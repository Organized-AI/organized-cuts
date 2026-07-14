#!/usr/bin/env bash
# Full pipeline for one session. Idempotent: skips media/ingest if already done,
# keeps existing clips.json, always (re)runs Whisper large-v3 + cut + upload.
#   scripts/run_session.sh /abs/path/to/session-dir
set -uo pipefail
export OC_PROJECT_DIR="$1"
export PATH="$HOME/.local/bin:$PATH"
cd /Users/supabowl/organized-cuts/jordan-close
PY=./.venv/bin/python
NAME="$(basename "$OC_PROJECT_DIR")"
echo "########## $NAME ##########"

$PY scripts/prepare_media.py            || { echo "!! $NAME prepare failed"; exit 1; }
$PY scripts/01_ingest.py                || { echo "!! $NAME ingest failed"; exit 1; }
if [ -f "$OC_PROJECT_DIR/analysis/transcript.json" ]; then
  echo "• transcript.json exists — skipping whisper"
else
  $PY scripts/whisper_transcript.py || { echo "!! $NAME whisper failed"; exit 1; }
fi
if [ ! -f "$OC_PROJECT_DIR/analysis/clips.json" ]; then
  $PY scripts/02_analyze.py             || { echo "!! $NAME analyze failed"; exit 1; }
else
  echo "• clips.json exists — keeping existing clips"
fi
$PY scripts/03_cut_reels.py             || { echo "!! $NAME cut failed"; exit 1; }
$PY scripts/05_loudnorm.py              || true
$PY scripts/04_pick_angle.py            || true
$PY scripts/06_report.py                || true

# stage with per-session names, then upload to the session's folder
UPLOAD="$($PY -c "import sys;sys.path.insert(0,'.');from lib import common as C;print(C.UPLOAD_FOLDER)")"
$PY - <<'PYEOF'
import json, os, sys; sys.path.insert(0, '.')
from lib import common as C
m = json.load(open(C.MANIFEST_PATH)); up = "20260713"
def tc(s):
    h=int(s//3600); mn=int((s%3600)//60); se=int(s%60); return f"{h:02d}-{mn:02d}-{se:02d}"
st = C.REELS/"upload"; st.mkdir(exist_ok=True)
for f in st.glob("*.mp4"): f.unlink()
nm = C.CFG.get("name","session")
for c in m["clips"]:
    os.link(C.REELS/f"reel_{c['id']}.mp4", st/f"{nm}_reel-{c['id']}_t{tc(c['start'])}_{up}_{c['kind']}.mp4")
print(f"staged {len(m['clips'])} reels")
PYEOF
rclone copy "$OC_PROJECT_DIR/reels/upload/" "gdrive:$UPLOAD/" --transfers 4 --stats-one-line 2>&1 | tail -1
rclone check "$OC_PROJECT_DIR/reels/upload/" "gdrive:$UPLOAD/" 2>&1 | grep -E "differences|matching"
echo "########## $NAME DONE ##########"
