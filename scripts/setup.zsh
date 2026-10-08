# Shared setup for the launchers: Python tools, whisper.cpp, ffmpeg and the Whisper model. Safe to run every time;
# it only installs what's missing. Sourced from the vault folder.
fail() { print "$1"; read; exit 1; }

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv || fail 'Python 3.10 or newer is required.'
fi
.venv/bin/python -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' || fail 'Python 3.10 or newer is required.'
if ! .venv/bin/python -c 'import yt_dlp' >/dev/null 2>&1; then
  print 'Installing yt-dlp (reads the YouTube playlist and downloads episode audio)…'
  .venv/bin/python -m pip install -q -r requirements.txt || fail 'Could not install yt-dlp. Check your internet connection and try again.'
fi

missing=()
command -v whisper-cli >/dev/null || missing+=(whisper-cpp)
command -v ffmpeg >/dev/null || missing+=(ffmpeg)
if (( ${#missing} )); then
  command -v brew >/dev/null || fail "Install Homebrew from https://brew.sh, then run: brew install ${missing[*]}"
  print "Installing ${missing[*]} with Homebrew…"
  brew install "${missing[@]}" || fail "Could not install ${missing[*]}. Run: brew install ${missing[*]}"
fi

model=models/ggml-large-v3-turbo-q5_0.bin
if [[ ! -s $model ]]; then
  print 'Downloading the Whisper model (about 550 MB, once)…'
  mkdir -p models
  curl -fL --progress-bar -o "$model.part" https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin \
    && mv "$model.part" "$model" || fail 'Could not download the Whisper model. Check your internet connection and try again.'
fi

command -v gh >/dev/null || print 'Note: install the GitHub CLI (brew install gh) and run "gh auth login" to save and publish quotes.'
