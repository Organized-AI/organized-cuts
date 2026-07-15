#!/usr/bin/env bash
# Add a SECOND, longer set of reels (0:45–1:30) to a session that already has its
# short reels done. Reuses the existing TwelveLabs index + Whisper transcript;
# only re-runs analyze→cut→loudnorm→report for the "long" variant, then stages
# with a _long filename tag and uploads into the SAME branded folder.
#
#   scripts/run_long.sh /abs/path/to/session-dir
set -uo pipefail
export OC_PROJECT_DIR="$1"
export OC_VARIANT=long
export PATH="$HOME/.local/bin:$PATH"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # jordan-close/
cd "$HERE"
PY=./.venv/bin/python
NAME="$(basename "$OC_PROJECT_DIR")"
echo "########## $NAME (long 0:45–1:30) ##########"

# The long run builds on the short run's ingest + transcript — don't re-do them.
if [ ! -f "$OC_PROJECT_DIR/analysis/state.json" ] || [ ! -f "$OC_PROJECT_DIR/analysis/transcript.json" ]; then
  echo "!! $NAME: missing analysis/state.json or transcript.json — run scripts/run_session.sh first"
  exit 1
fi

$PY scripts/02_analyze.py    || { echo "!! $NAME analyze(long) failed"; exit 1; }
$PY scripts/03_cut_reels.py  || { echo "!! $NAME cut(long) failed"; exit 1; }
$PY scripts/05_loudnorm.py   || true
$PY scripts/04_pick_angle.py || true
$PY scripts/06_report.py     || true

# Stage the long reels with a _long tag and upload to the same branded folder.
UPLOAD="$($PY -c "import sys;sys.path.insert(0,'.');from lib import common as C;print(C.UPLOAD_FOLDER)")"
REELS_DIR="$($PY -c "import sys;sys.path.insert(0,'.');from lib import common as C;print(C.REELS)")"
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
    os.link(C.REELS/f"reel_{c['id']}.mp4",
            st/f"{nm}_reel-{c['id']}_t{tc(c['start'])}_{up}_{c['kind']}_long.mp4")
print(f"staged {len(m['clips'])} long reels")
PYEOF
rclone copy "$REELS_DIR/upload/" "gdrive:$UPLOAD/" --transfers 4 --stats-one-line 2>&1 | tail -1
rclone check "$REELS_DIR/upload/" "gdrive:$UPLOAD/" 2>&1 | grep -E "differences|matching"
echo "########## $NAME (long) DONE ##########"
