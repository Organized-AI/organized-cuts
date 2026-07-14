#!/usr/bin/env bash
# One-time environment setup on a new machine (e.g. claws-mac-mini).
# Run from the code dir:  cd ~/organized-cuts/jordan-close && bash scripts/setup_mini.sh
set -uo pipefail
cd "$(dirname "$0")/.."

echo "=== 1. ffmpeg + videotoolbox ==="
if ! command -v ffmpeg >/dev/null; then
  echo "!! ffmpeg missing — install it:  brew install ffmpeg"; exit 1
fi
ffmpeg -hide_banner -encoders 2>/dev/null | grep -q h264_videotoolbox \
  && echo "ok: h264_videotoolbox present" \
  || echo "!! WARNING: h264_videotoolbox not found — reels will fall back to slow CPU x264"

echo "=== 2. python venv + deps ==="
PY=python3.13; command -v $PY >/dev/null || PY=python3
$PY -m venv .venv
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r requirements.txt faster-whisper pillow "opencv-python-headless<5"
./.venv/bin/python -c "import twelvelabs,cv2,PIL,faster_whisper; print('deps ok; opencv',cv2.__version__)"

echo "=== 3. Playfair Display font ==="
mkdir -p assets/fonts
if [ ! -f assets/fonts/PlayfairDisplay-Italic-var.ttf ]; then
  curl -fsSL -o assets/fonts/PlayfairDisplay-Italic-var.ttf \
    "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf" \
    && echo "font downloaded" || echo "!! font download failed (captions fall back to system serif)"
else
  echo "ok: font present"
fi

echo "=== 4. rclone ==="
if command -v rclone >/dev/null; then
  echo "ok: $(rclone version | head -1)"
else
  echo "installing rclone static binary…"
  tmp=$(mktemp -d); curl -fsSL -o "$tmp/r.zip" https://downloads.rclone.org/rclone-current-osx-arm64.zip
  unzip -oq "$tmp/r.zip" -d "$tmp"; mkdir -p ~/.local/bin
  cp "$tmp"/rclone-*/rclone ~/.local/bin/rclone && chmod +x ~/.local/bin/rclone
  echo "installed to ~/.local/bin/rclone (add ~/.local/bin to PATH)"
fi
rclone listremotes 2>/dev/null | grep -q '^gdrive:' \
  && echo "ok: gdrive remote configured" \
  || echo "!! gdrive remote missing — copy ~/.config/rclone/rclone.conf from the MBP"

echo "=== 5. secrets ==="
grep -q TWELVELABS_API_KEY .env 2>/dev/null && echo "ok: .env has key" || echo "!! .env missing TWELVELABS_API_KEY"

echo "=== setup complete ==="
