#!/usr/bin/env python3
"""Transcribe Regulation Podcast YouTube videos locally with whisper.cpp, so candidate timestamps match YouTube.

Audio is downloaded one video at a time, transcribed on this Mac, then deleted. Transcripts are kept in
`transcripts/` (gitignored) so a video is never transcribed twice. Candidates go to `drafts/` through the same
importer as captions: unverified, no speakers, nothing published.

    python3 scripts/whisper_youtube.py --video VIDEO_ID     # one video (prints where the transcript went)
    python3 scripts/whisper_youtube.py --batch 5            # the next 5 numbered episodes not yet transcribed
"""
import argparse
import json
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from collect_youtube import collect

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "ggml-large-v3-turbo-q5_0.bin"
TRANSCRIPTS = ROOT / "transcripts"
STATE_PATH = "inbox/whisper_processed.json"
# A punctuated, capitalized prompt keeps Whisper writing full sentences (the importer needs sentence endings) and
# spells the cast and recurring names the way the show does.
PROMPT = ("Welcome to the Regulation Podcast. I'm Geoff, and I'm here with Andrew, Gavin, Eric and Nick. "
          "Today we're talking about Rooster Teeth, Achievement Hunter and the F**kface days. It's going to be great!")


def _whisper_cli():
    path = shutil.which("whisper-cli")
    if not path:
        raise RuntimeError("whisper.cpp is missing. Install it with: brew install whisper-cpp")
    if not MODEL.exists():
        raise RuntimeError(f"Whisper model missing at {MODEL}. See README: Whisper transcription.")
    return path


def download_audio(video_id, folder):
    """Audio only, one file, into [folder]."""
    import yt_dlp
    options = {"format": "bestaudio/best", "outtmpl": str(Path(folder) / "%(id)s.%(ext)s"), "quiet": True,
               "no_warnings": True, "noplaylist": True, "socket_timeout": 20, "extractor_retries": 1, "noprogress": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
        return Path(ydl.prepare_filename(info))


def transcribe(video_id, log=print):
    """Timed segments ({text, start, duration}) for a YouTube video, from the cache or a fresh Whisper run."""
    TRANSCRIPTS.mkdir(exist_ok=True)
    cached = TRANSCRIPTS / f"{video_id}.json"
    if cached.exists():
        return json.loads(cached.read_text())["segments"]
    cli = _whisper_cli()
    with tempfile.TemporaryDirectory(prefix="whisper_") as tmp:
        began = time.time()
        audio = download_audio(video_id, tmp)
        wav = Path(tmp) / "audio.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(audio), "-ar", "16000", "-ac", "1", str(wav)], check=True)
        audio.unlink()
        downloaded = time.time()
        out = Path(tmp) / "out"
        subprocess.run([cli, "-m", str(MODEL), "-f", str(wav), "-l", "en", "--prompt", PROMPT, "-oj", "-of", str(out), "-np"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        rows = json.loads((out.with_suffix(".json")).read_text(errors="replace")).get("transcription", [])
        segments = []
        for row in rows:
            # Whisper hears "Jeff"; the show spells him Geoff.
            text = re.sub(r"\bJeff\b", "Geoff", " ".join(str(row.get("text", "")).split()))
            if not text:
                continue
            start = row["offsets"]["from"] / 1000
            segments.append({"text": text, "start": start, "duration": max(0.0, row["offsets"]["to"] / 1000 - start)})
        log(f"{video_id}: download {downloaded - began:.0f}s, transcribe {time.time() - downloaded:.0f}s, {len(segments)} segments")
    cached.write_text(json.dumps({"youtubeVideoId": video_id, "model": MODEL.name, "segments": segments}, ensure_ascii=False) + "\n")
    return segments


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video", help="Transcribe one YouTube video ID (no drafts written)")
    group.add_argument("--batch", type=int, help="Transcribe this many numbered episodes and save draft candidates")
    args = parser.parse_args()
    if args.video:
        segments = transcribe(args.video)
        print(f"{len(segments)} segments saved to {TRANSCRIPTS / (args.video + '.json')}")
    else:
        result = collect(target=10 * args.batch, max_videos=args.batch, fetch_transcript_fn=transcribe,
                         state_path=STATE_PATH, delay_seconds=10)
        print(result)
