#!/bin/zsh
cd -- "$(dirname -- "$0")" || exit 1
source scripts/setup.zsh
print 'Open the Review dashboard address shown below in your browser. Keep this window open while reviewing.'
exec .venv/bin/python scripts/review_server.py
