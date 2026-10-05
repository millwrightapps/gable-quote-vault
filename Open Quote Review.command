#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv || { print 'Python 3.10 or newer is required.'; read; exit 1; }
fi
if ! .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  print 'Python 3.10 or newer is required.'
  read
  exit 1
fi
if ! .venv/bin/python -c 'import yt_dlp, youtube_transcript_api' >/dev/null 2>&1; then
  print 'Installing the free YouTube transcript tools for this dashboard…'
  .venv/bin/python -m pip install -r requirements.txt || { print 'Could not install the transcript tools. Check your internet connection and try again.'; read; exit 1; }
fi
print 'Open http://127.0.0.1:8765 in your browser. Refresh queue will read transcripts from YouTube on this Mac.'
exec .venv/bin/python scripts/review_server.py
