#!/usr/bin/env python3
"""
Automated transcript scraper for podcast episodes.
Fetches recent video IDs via yt-dlp, extracts transcripts via
youtube-transcript-api, and saves clean files to inbox/.
"""

import os
import re
import sys
from pathlib import Path
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# Configure the target source: can be a channel URL, playlist URL, or channel handles
# Example: "https://www.youtube.com/@RegulationPodcast/videos"
SOURCE_URL = os.environ.get("PODCAST_SOURCE_URL", "https://www.youtube.com/playlist?list=PL0YaZqNO5Z3ds7_sVSEP-FTjvvfWWWY8O")

# Maximum number of recent episodes to inspect per run
MAX_EPISODES = int(os.environ.get("MAX_EPISODES", "10"))

# Target output directory relative to repo root
OUTPUT_DIR = Path("inbox")


def sanitize_filename(name: str) -> str:
    """Sanitize strings for safe file naming."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def get_existing_ids(output_path: Path) -> set[str]:
    """Scan existing transcripts in repo to avoid redundant scraping."""
    existing_ids = set()
    if not output_path.exists():
        return existing_ids

    # Search for stored video IDs in existing file names or headers
    for file_path in output_path.glob("*.md"):
        # Match pattern [VIDEO_ID] if embedded in filename
        match = re.search(r"\[([a-zA-Z0-9_-]{11})\]", file_path.name)
        if match:
            existing_ids.add(match.group(1))
    return existing_ids


def fetch_recent_videos(source_url: str, limit: int = 10) -> list[dict]:
    """Fetch video metadata using yt-dlp flat extraction (fast, no download)."""
    ydl_opts = {
        "extract_flat": True,
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


def fetch_transcript_text(video_id: str) -> str | None:
    """Retrieve full transcript formatted with timestamps."""
    try:
        transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US"])
    except (TranscriptsDisabled, NoTranscriptFound):
        # Try fetching auto-generated transcript if manual transcript is unavailable
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_generated_transcript(["en", "en-US"])
            transcript_data = transcript.fetch()
        except Exception:
            return None
    except Exception as e:
        print(f"[!] Transcript error for {video_id}: {e}", file=sys.stderr)
        return None

    lines = []
    for item in transcript_data:
        start_secs = int(item["start"])
        minutes = start_secs // 60
        seconds = start_secs % 60
        timestamp = f"{minutes:02d}:{seconds:02d}"
        text = item["text"].replace("\n", " ").strip()
        lines.append(f"[{timestamp}] {text}")

    return "\n".join(lines)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_ids = get_existing_ids(OUTPUT_DIR)
    
    # Also check quotes/ or drafts/ if files are moved downstream
    for folder in [Path("drafts"), Path("quotes"), Path("published")]:
        existing_ids.update(get_existing_ids(folder))

    print(f"[*] Checking {SOURCE_URL} for recent episodes...")
    recent_videos = fetch_recent_videos(SOURCE_URL, limit=MAX_EPISODES)

    if not recent_videos:
        print("[-] No videos found or failed to fetch playlist.")
        return

    new_count = 0
    for vid in recent_videos:
        video_id = vid["id"]
        title = vid["title"]

        if video_id in existing_ids:
            print(f"[-] Skipping already processed: {title} ({video_id})")
            continue

        print(f"[+] Processing: {title} ({video_id})")
        transcript = fetch_transcript_text(video_id)

        if not transcript:
            print(f"    [!] No transcript available for {video_id}. Skipping.")
            continue

        safe_title = sanitize_filename(title)
        filename = f"{safe_title} [{video_id}].md"
        out_file = OUTPUT_DIR / filename

        content = (
            f"# {title}\n\n"
            f"- **Source:** https://www.youtube.com/watch?v={video_id}\n"
            f"- **Video ID:** {video_id}\n\n"
            f"## Transcript\n\n"
            f"{transcript}\n"
        )

        out_file.write_text(content, encoding="utf-8")
        print(f"    -> Saved to {out_file}")
        new_count += 1

    print(f"\n[✓] Done. Added {new_count} new transcript(s).")


if __name__ == "__main__":
    main()
