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
review_interface=$(/sbin/route -n get default | /usr/bin/awk '/interface:/{print $2}')
review_address=$(/usr/sbin/ipconfig getifaddr "$review_interface")
if [[ -z "$review_address" ]]; then
  print 'Connect your Mac to your home network, then try again.'
  read
  exit 1
fi
print 'Keep this window open. Use the phone address and pairing code printed below.'
exec .venv/bin/python scripts/review_server.py --lan-ip "$review_address"
