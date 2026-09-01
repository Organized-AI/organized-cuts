#!/usr/bin/env bash
# Build widgets for every session in talks/registry.json, then merge the bundle.
# Continues past sessions that have not been analyzed yet.
#
#   bash scripts/widgets_all.sh              # live: fills gaps from TwelveLabs
#   bash scripts/widgets_all.sh --offline    # local artifacts only, no API calls
set -uo pipefail
export CODE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="${OC_REPO_ROOT:-$(cd "$CODE_DIR/.." && pwd)}"
PY="${OC_PYTHON:-$CODE_DIR/.venv/bin/python}"
[ -x "$PY" ] || PY=python3

SESSIONS=$("$PY" - <<'PYEOF'
import json, os, pathlib, sys
sys.path.insert(0, os.environ["CODE_DIR"])
from lib import talkmap as T
for t in T.load_registry()["talks"]:
    for s in t["sessions"]:
        print(s)
PYEOF
) || { echo "!! could not read the talk registry"; exit 1; }

FAIL=()
for s in $SESSIONS; do
  if [ ! -d "$REPO_ROOT/$s" ]; then
    echo "-- $s: no such session dir; skipping"
    continue
  fi
  echo ">>>>>>>>>> $s"
  if OC_PROJECT_DIR="$REPO_ROOT/$s" "$PY" "$CODE_DIR/scripts/07_widgets.py" "$@"; then :; else
    echo "!! $s failed"; FAIL+=("$s")
  fi
done

echo ">>>>>>>>>> merge"
"$PY" "$CODE_DIR/scripts/08_talkmap.py" || { echo "!! merge failed"; exit 1; }
echo "=================================="
echo "WIDGETS COMPLETE. Failures: ${FAIL[*]:-none}"
