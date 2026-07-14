#!/usr/bin/env bash
# Promote the best screen-content talk clips to 'demo' (screenshare + speaker),
# re-cut/loudnorm/report those clips, and re-upload the session.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
OC=/Users/supabowl/organized-cuts
PYDIR=$OC/jordan-close
PY=$PYDIR/.venv/bin/python

# session:how_many_to_promote  (to reach 5 demo reels each)
JOBS=(
  "session-1-esteban:5" "session-2-ct:4"  "session-3-rohit:3"  "session-3a-rohit:5"
  "session-4-michael:5" "session-5-michael:3" "session-5a-michael:4" "session-6a-shep:2"
)

for j in "${JOBS[@]}"; do
  s="${j%%:*}"; n="${j##*:}"
  echo "########## $s (promote $n to demo) ##########"
  export OC_PROJECT_DIR="$OC/$s"
  ids=$($PY "$PYDIR/scripts/demo_candidates.py" --promote "$n" </dev/null | grep '^PROMOTED ' | sed 's/^PROMOTED //')
  [ -z "${ids:-}" ] && { echo "!! no promotions for $s"; continue; }
  echo "  promoted -> $ids"
  $PY "$PYDIR/scripts/03_cut_reels.py" --only "$ids" </dev/null || { echo "!! cut failed $s"; continue; }
  $PY "$PYDIR/scripts/05_loudnorm.py" --only "$ids" </dev/null || true
  $PY "$PYDIR/scripts/04_pick_angle.py" </dev/null >/dev/null || true
  $PY "$PYDIR/scripts/06_report.py"     </dev/null >/dev/null || true

  UPLOAD=$($PY -c "import sys;sys.path.insert(0,'$PYDIR');from lib import common as C;print(C.UPLOAD_FOLDER)" </dev/null)
  $PY - <<PYEOF </dev/null
import json, os, sys
sys.path.insert(0, "$PYDIR")
from lib import common as C
m = json.load(open(C.MANIFEST_PATH)); up = "20260713"
def tc(s):
    h=int(s//3600); mn=int((s%3600)//60); se=int(s%60); return f"{h:02d}-{mn:02d}-{se:02d}"
st = C.REELS/"upload"; st.mkdir(exist_ok=True)
for f in st.glob("*.mp4"): f.unlink()
nm = C.CFG.get("name","session")
for c in m["clips"]:
    os.link(C.REELS/f"reel_{c['id']}.mp4", st/f"{nm}_reel-{c['id']}_t{tc(c['start'])}_{up}_{c['kind']}.mp4")
print("staged", len(m["clips"]))
PYEOF
  rclone copy "$OC_PROJECT_DIR/reels/upload/" "gdrive:$UPLOAD/" --transfers 4 --stats-one-line </dev/null 2>&1 | tail -1
  echo "########## $s DONE ##########"
done
echo "ALL DEMO FIXES DONE"
