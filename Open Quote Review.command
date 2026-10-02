#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
print 'Open http://127.0.0.1:8765 in your browser. Keep this window open while reviewing.'
python3 scripts/review_server.py
