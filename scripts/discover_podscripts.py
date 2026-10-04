#!/usr/bin/env python3
"""
Automated podcast scraper and lore scrubber.
Extracts recent episode transcripts via yt-dlp and youtube-transcript-api,
cross-references lines against lore_terms.py and quote_filters.py,
and commits structured markdown to inbox/.
"""

import os
import re
import sys
from pathlib import Path
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# Import internal repository scrubbers and filters
from lore_terms import matches
from quote_filters import is_ad_or_sponsored

# Target playlist URL (Regulation Podcast official playlist)
DEFAULT_PLAYLIST = "https://www.youtube.com/playlist?list=PL0YaZqNO5Z3ds7_sVSEP-FTjvvfWWWY8O"
SOURCE_URL = os.environ.get("PODCAST_SOURCE_URL", DEFAULT_PLAYLIST)

# Limit how many recent episodes to check per run
MAX_EPISODES = int(os.environ.get("MAX_EPISODES", "10"))

# Target output directories
REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "inbox"


def sanitize_filename(name: str) -> str:
    """Sanitize strings for safe file naming."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def format_timestamp(seconds: float) -> str:
    """Format total seconds into HH:MM:SS or MM:SS."""
    secs = int(seconds)
    hours, remainder = divmod(secs, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def get_existing_ids() -> set[str]:
    """Scan existing files across folders to avoid redundant work."""
    existing_ids = set()
    for folder in [REPO_ROOT / "inbox", REPO_ROOT / "drafts", REPO_ROOT / "quotes", REPO_ROOT / "published"]:
        if not folder.exists():
            continue
        for file_path in folder.glob("*.md"):
            match = re.search(r"\[([a-zA-Z0-9_-]{11})\]", file_path.name)
            if match:
                existing_ids.add(match.group(1))
    return existing_ids


def fetch_recent_videos(source_url: str, limit: int = 10) -> list[dict]:
    """Fetch video metadata using yt-dlp reversed to catch newest additions."""
    ydl_opts = {
        "extract_flat": True,
        "playlistreverse": True,
        "playlistend": limit,
        "quiet": True,
        "no_warnings": True,
    }

    videos = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(source_url, download=False)
            entries = info.get("entries") or []
            for entry in entries:
                if entry and entry.get("id"):
                    videos.append({
                        "id": entry["id"],
                        "title": entry.get("title", f"Episode {entry['id']}"),
                        "url": entry.get("url", f"https://www.youtube.com/watch?v={entry['id']}"),
                    })
        except Exception as e:
            print(f"[!] Error fetching metadata from {source_url}: {e}", file=sys.stderr)

    return videos


def fetch_raw_transcript(video_id: str) -> list[dict] | None:
    """Retrieve raw transcript chunks with start offsets and text."""
    try:
        return YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US"])
    except (TranscriptsDisabled, NoTranscriptFound):
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_generated_transcript(["en", "en-US"])
            return transcript.fetch()
        except Exception:
            return None
    except Exception as e:
        print(f"[!] Transcript fetch error for {video_id}: {e}", file=sys.stderr)
        return None


def extract_lore_candidates(transcript_items: list[dict], window: int = 2) -> list[dict]:
    """
    Scans lines with lore_terms.matches(), verifies they are not sponsored/ad reads,
    and returns snippet windows with context lines.
    """
    candidates = []
    seen_indices = set()

    for idx, item in enumerate(transcript_items):
        text = item["text"]
        
        # Check against quote_filters to ignore sponsor blocks
        if is_ad_or_sponsored(text):
            continue

        matched_terms = matches(text)
        if matched_terms and idx not in seen_indices:
            # Capture context lines around the hit
            start_idx = max(0, idx - window)
            end_idx = min(len(transcript_items), idx + window + 1)

            for i in range(start_idx, end_idx):
                seen_indices.add(i)

            snippet_lines = []
            for sub_item in transcript_items[start_idx:end_idx]:
                ts = format_timestamp(sub_item["start"])
                clean_text = sub_item["text"].replace("\n", " ").strip()
                snippet_lines.append(f"[{ts}] {clean_text}")

            candidates.append({
                "terms": matched_terms,
                "timestamp": format_timestamp(item["start"]),
                "block": "\n".join(snippet_lines),
            })

    return candidates


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_ids = get_existing_ids()

    print(f"[*] Checking {SOURCE_URL} for recent episodes...")
    recent_videos = fetch_recent_videos(SOURCE_URL, limit=MAX_EPISODES)

    if not recent_videos:
        print("[-] No videos found or playlist could not be read.")
        return

    new_count = 0
    for vid in recent_videos:
        video_id = vid["id"]
        title = vid["title"]

        if video_id in existing_ids:
            print(f"[-] Already recorded: {title} ({video_id})")
            continue

        print(f"[+] Processing: {title} ({video_id})")
        transcript_items = fetch_raw_transcript(video_id)

        if not transcript_items:
            print(f"    [!] No captions available for {video_id}. Skipping.")
            continue

        # 1. Scrub for lore matches
        lore_candidates = extract_lore_candidates(transcript_items)

        # 2. Build full timestamped transcript text
        full_transcript_lines = []
        for item in transcript_items:
            ts = format_timestamp(item["start"])
            clean_text = item["text"].replace("\n", " ").strip()
            full_transcript_lines.append(f"[{ts}] {clean_text}")
        full_transcript_body = "\n".join(full_transcript_lines)

        # 3. Format candidate section
        candidate_section = "## Flagged Lore Candidates\n\n"
        if lore_candidates:
            for c in lore_candidates:
                terms_str = ", ".join(f"`{t}`" for t in c["terms"])
                candidate_section += (
                    f"### {terms_str} (at {c['timestamp']})\n\n"
                    f"```text\n{c['block']}\n```\n\n"
                )
        else:
            candidate_section += "_No dictionary lore terms detected in this episode._\n\n"

        # 4. Construct file content and write
        file_content = (
            f"# {title}\n\n"
            f"- **Source:** https://www.youtube.com/watch?v={video_id}\n"
            f"- **Video ID:** {video_id}\n\n"
            f"{candidate_section}"
            f"## Full Transcript\n\n"
            f"{full_transcript_body}\n"
        )

        safe_title = sanitize_filename(title)
        out_file = OUTPUT_DIR / f"{safe_title} [{video_id}].md"
        out_file.write_text(file_content, encoding="utf-8")
        print(f"    -> Saved to {out_file.relative_to(REPO_ROOT)} ({len(lore_candidates)} lore moments found)")
        new_count += 1

    print(f"\n[✓] Done. Added {new_count} episode transcript(s) to inbox.")


if __name__ == "__main__":
    main()
