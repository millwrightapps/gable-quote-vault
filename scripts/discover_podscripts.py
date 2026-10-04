#!/usr/bin/env python3
"""
Automated podcast scraper and lore scrubber.
Extracts recent episode transcripts via yt-dlp flat playlist discovery
and direct timedtext retrieval, cross-references against lore_terms.py
and quote_filters.py, and commits structured markdown to inbox/.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# Add scripts directory to path so relative imports work inside GitHub Actions runner
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yt_dlp

# Import lore dictionary matching function
try:
  from lore_terms import matches
except ImportError:

  def matches(text: str) -> list[str]:
    return []


# Safe import for quote_filters
try:
  import quote_filters

  if hasattr(quote_filters, "is_ad_or_sponsored"):
    is_ad_or_sponsored = quote_filters.is_ad_or_sponsored
  elif hasattr(quote_filters, "is_ad"):
    is_ad_or_sponsored = quote_filters.is_ad
  elif hasattr(quote_filters, "is_sponsored"):
    is_ad_or_sponsored = quote_filters.is_sponsored
  elif hasattr(quote_filters, "filter_ads"):
    is_ad_or_sponsored = quote_filters.filter_ads
  else:

    def is_ad_or_sponsored(text: str) -> bool:
      return False
except ImportError:

  def is_ad_or_sponsored(text: str) -> bool:
    return False


# Target playlist URL (Regulation Podcast official playlist)
DEFAULT_PLAYLIST = (
    "https://www.youtube.com/playlist?list=PL0YaZqNO5Z3ds7_sVSEP-FTjvvfWWWY8O"
)
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
  for folder in [
      REPO_ROOT / "inbox",
      REPO_ROOT / "drafts",
      REPO_ROOT / "quotes",
      REPO_ROOT / "published",
  ]:
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
          title = entry.get("title") or f"Episode {entry['id']}"
          # Skip deleted or unavailable placeholder entries
          if (
              title in ["[Deleted video]", "[Private video]"]
              or "Episode " in title
              and len(title) == 19
          ):
            if not entry.get("title"):
              continue
          videos.append({
              "id": entry["id"],
              "title": title,
              "url": (
                  entry.get("url")
                  or f"https://www.youtube.com/watch?v={entry['id']}"
              ),
          })
    except Exception as e:
      print(
          f"[!] Error fetching metadata from {source_url}: {e}", file=sys.stderr
      )
  return videos


def fetch_raw_transcript(video_id: str) -> list[dict] | None:
  """Directly query YouTube's Innertube API and timedtext caption servers.

  Uses the Android client endpoint to bypass web bot-check walls on cloud
  runners.
  """
  # 1. Fetch caption tracks metadata from Innertube API endpoint using ANDROID client
  api_url = "https://www.youtube.com/youtubei/v1/player"
  payload = {
      "context": {
          "client": {
              "clientName": "ANDROID",
              "clientVersion": "19.29.35",
              "hl": "en",
              "gl": "US",
              "androidSdkVersion": 34,
          }
      },
      "videoId": video_id,
  }
  headers = {
      "Content-Type": "application/json",
      "User-Agent": (
          "com.google.android.youtube/19.29.35 (Linux; U; Android 14) gzip"
      ),
  }

  try:
    req = urllib.request.Request(
        api_url, data=json.dumps(payload).encode("utf-8"), headers=headers
    )
    with urllib.request.urlopen(req, timeout=10) as response:
      data = json.loads(response.read().decode("utf-8"))

    playability = data.get("playabilityStatus", {})
    status = playability.get("status")
    if status not in ("OK", None):
      reason = playability.get("reason", "Unknown block")
      print(f"    [!] Playability warning ({status}): {reason}", file=sys.stderr)

    captions_obj = data.get("captions", {}).get(
        "playerCaptionsTracklistRenderer", {}
    )
    tracks = captions_obj.get("captionTracks", [])
    if not tracks:
      return None

    # Prioritize English tracks
    selected_track = None
    for track in tracks:
      lang = track.get("languageCode", "")
      if lang.startswith("en"):
        selected_track = track
        break
    if not selected_track:
      selected_track = tracks[0]

    base_url = selected_track.get("baseUrl")
    if not base_url:
      return None

    # Request standard XML timedtext
    sub_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
    }
    sub_req = urllib.request.Request(base_url, headers=sub_headers)
    with urllib.request.urlopen(sub_req, timeout=10) as sub_res:
      xml_data = sub_res.read().decode("utf-8")

    # Parse caption nodes
    root = ET.fromstring(xml_data)
    items = []
    for elem in root.findall(".//text"):
      text = elem.text or ""
      text = (
          text.replace("&#39;", "'")
          .replace("&amp;", "&")
          .replace("&quot;", '"')
          .replace("\n", " ")
          .strip()
      )
      if not text:
        continue
      start = float(elem.attrib.get("start", 0.0))
      duration = float(elem.attrib.get("dur", 0.0))
      items.append({"text": text, "start": start, "duration": duration})

    return items if items else None

  except Exception as e:
    print(f"    [!] Timedtext fetch error for {video_id}: {e}", file=sys.stderr)
    return None


def extract_lore_candidates(
    transcript_items: list[dict], window: int = 2
) -> list[dict]:
  """Scans lines with lore_terms.matches(), verifies they are not sponsored/ad reads,

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
      candidate_section += (
          "_No dictionary lore terms detected in this episode._\n\n"
      )

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
    print(
        f"    -> Saved to {out_file.relative_to(REPO_ROOT)} ("
        f"{len(lore_candidates)} lore moments found)"
    )
    new_count += 1

  print(f"\n[✓] Done. Added {new_count} episode transcript(s) to inbox.")


if __name__ == "__main__":
  main()
