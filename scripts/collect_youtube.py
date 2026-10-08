#!/usr/bin/env python3
"""Collect unattributed candidates from the RP YouTube playlist, transcribed locally (see whisper_youtube.py)."""
import json
from pathlib import Path
import re
import time

from import_transcript import candidates
from quote_duplicates import existing_wording

ROOT = Path(__file__).resolve().parents[1]
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL0YaZqNO5Z3ds7_sVSEP-FTjvvfWWWY8O"
STATE_PATH = "inbox/whisper_processed.json"
COOLDOWN_SECONDS = 30 * 60


def fetch_videos(limit=1000):
    """Read playlist metadata only (titles and IDs)."""
    try:
        import yt_dlp
    except ImportError as error:
        raise RuntimeError("yt-dlp is missing. Close the dashboard and reopen Open Quote Review.command to install it.") from error

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


def _state(root, path=None):
    path = path or root / STATE_PATH
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
    ) or "too many requests" in text or "rate limit" in text or "429" in text or "not a bot" in text


def _unavailable(error):
    text = str(error).lower()
    return "video unavailable" in text or "private video" in text or "members-only" in text


def collect(fetch_transcript_fn, root=ROOT, target=10, max_videos=20, fetch_videos_fn=None,
            delay_seconds=5, now_fn=time.time, sleep_fn=time.sleep, state_path=STATE_PATH):
    """Fetch from YouTube on the local machine and save only draft excerpts."""
    root = Path(root)
    for folder in ("drafts", "quotes", "inbox", "quarantine"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    state_path = root / state_path
    state = _state(root, state_path)
    processed = set(state["processed"])
    now = now_fn()
    if state["cooldownUntil"] > now:
        return {"added": 0, "checked": 0, "retryAfter": int(state["cooldownUntil"] - now) + 1}

    fetch_videos_fn = fetch_videos_fn or fetch_videos
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
                break  # Leave this video unprocessed so the next run can retry it.
            if _unavailable(error):
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
