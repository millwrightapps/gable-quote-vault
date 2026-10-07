#!/usr/bin/env python3
"""Collect unattributed transcript candidates from the RP YouTube playlist locally."""
import html
import json
from pathlib import Path
import re
import time

from import_transcript import candidates
from quote_duplicates import existing_wording

ROOT = Path(__file__).resolve().parents[1]
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL0YaZqNO5Z3ds7_sVSEP-FTjvvfWWWY8O"
STATE_PATH = "inbox/youtube_processed.json"
COOLDOWN_SECONDS = 30 * 60


def fetch_videos(limit=1000):
    """Read playlist metadata only; transcript requests run from the dashboard host."""
    try:
        import yt_dlp
    except ImportError as error:
        raise RuntimeError("YouTube tools are missing. Close the dashboard and reopen Open Quote Review.command to install them.") from error

    options = {
        "extract_flat": True,
        "playlistreverse": True,
        "playlistend": limit,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "socket_timeout": 20,
        "extractor_retries": 1,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(PLAYLIST_URL, download=False)
    except Exception as error:
        detail = " ".join(str(error).split())[:240]
        raise RuntimeError(f"Could not read the YouTube playlist from this Mac: {detail}") from error
    entries = (info or {}).get("entries") or []
    videos = []
    for entry in entries:
        if not entry or not entry.get("id"):
            continue
        title = (entry.get("title") or "").strip()
        if not title or title in ("[Deleted video]", "[Private video]"):
            continue
        videos.append({"id": entry["id"], "title": title})
    if not videos:
        raise RuntimeError("YouTube returned no playlist videos. Check the connection and try again later.")
    return videos


def fetch_transcript(video_id):
    """Fetch English captions with the current youtube-transcript-api interface."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as error:
        raise RuntimeError("YouTube tools are missing. Close the dashboard and reopen Open Quote Review.command to install them.") from error

    fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en", "en-US", "en-GB"])
    raw = fetched.to_raw_data()
    return [
        {"text": html.unescape(str(row.get("text", ""))).replace("\n", " ").strip(),
         "start": float(row.get("start", 0)), "duration": float(row.get("duration", 0))}
        for row in raw if str(row.get("text", "")).strip()
    ]


def _state(root):
    path = root / STATE_PATH
    if not path.exists():
        return {"processed": [], "cooldownUntil": 0}
    state = json.loads(path.read_text())
    if isinstance(state, list):
        return {"processed": state, "cooldownUntil": 0}
    return {"processed": state.get("processed", []), "cooldownUntil": state.get("cooldownUntil", 0)}


def _is_youtube_block(error):
    name = type(error).__name__.lower()
    text = str(error).lower()
    return name in {"requestblocked", "ipblocked"} or "ipblocked" in name or (
        "blocked" in text and ("youtube" in text or "ip" in text)
    ) or "too many requests" in text or "rate limit" in text or "429" in text


def _has_no_transcript(error):
    return type(error).__name__ in {"NoTranscriptFound", "TranscriptsDisabled", "VideoUnavailable"}


def collect(root=ROOT, target=10, max_videos=20, fetch_videos_fn=None,
            fetch_transcript_fn=None, delay_seconds=5, now_fn=time.time, sleep_fn=time.sleep):
    """Fetch from YouTube on the local machine and save only draft excerpts."""
    root = Path(root)
    for folder in ("drafts", "quotes", "inbox", "quarantine"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    state_path = root / STATE_PATH
    state = _state(root)
    processed = set(state["processed"])
    now = now_fn()
    if state["cooldownUntil"] > now:
        return {"added": 0, "checked": 0, "retryAfter": int(state["cooldownUntil"] - now) + 1}

    fetch_videos_fn = fetch_videos_fn or fetch_videos
    fetch_transcript_fn = fetch_transcript_fn or fetch_transcript
    try:
        videos = fetch_videos_fn()
    except Exception as error:
        if not _is_youtube_block(error):
            raise
        cooldown_until = now_fn() + COOLDOWN_SECONDS
        state_path.write_text(json.dumps({"processed": sorted(processed),
                                          "cooldownUntil": cooldown_until}, indent=2) + "\n")
        return {"added": 0, "checked": 0, "retryAfter": COOLDOWN_SECONDS}
    known = existing_wording(root)
    added = checked = 0
    cooldown_until = 0
    for video in videos:
        video_id, title = video["id"], video["title"]
        if video_id in processed:
            continue
        if checked >= max_videos or added >= target:
            break
        episode = re.search(r"\[(\d+)\]\s*$", title)
        if not episode:
            # Supplemental videos without an explicit episode number need manual entry.
            processed.add(video_id)
            continue

        if checked and delay_seconds:
            sleep_fn(delay_seconds)
        try:
            segments = fetch_transcript_fn(video_id)
        except Exception as error:
            if _is_youtube_block(error):
                cooldown_until = now_fn() + COOLDOWN_SECONDS
                break  # Leave this video unprocessed so Refresh queue can retry later.
            if _has_no_transcript(error):
                processed.add(video_id)
                checked += 1
                continue
            # Don't mark transient errors as processed; a later refresh can retry them.
            checked += 1
            continue

        transcript = dict(youtubeVideoId=video_id, show="RP", episode=int(episode.group(1)),
                          episodeTitle=title, segments=segments)
        for quote in candidates(transcript, known)[:max(0, target - added)]:
            path = root / "drafts" / (quote["id"] + ".json")
            if path.exists() or (root / "quotes" / path.name).exists():
                continue
            path.write_text(json.dumps(quote, indent=2, ensure_ascii=False) + "\n")
            known.append(quote["quote"])
            added += 1
        processed.add(video_id)
        checked += 1

    state_path.write_text(json.dumps({"processed": sorted(processed),
                                      "cooldownUntil": cooldown_until}, indent=2) + "\n")
    result = {"added": added, "checked": checked}
    if cooldown_until:
        result["retryAfter"] = COOLDOWN_SECONDS
    return result
