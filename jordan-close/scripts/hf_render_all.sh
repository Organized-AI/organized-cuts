#!/usr/bin/env bash
# Render the animated series: for each selected clip, cut assets once, then
# render each variant (pip, split). Idempotent (skips finished outputs).
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
OC=/Users/supabowl/organized-cuts
HF=$OC/animated/hf
PYDIR=$OC/jordan-close
PY=$PYDIR/.venv/bin/python
OUT=$HF/renders/final; mkdir -p "$OUT"
SEL=$OC/animated/selection.json
VARIANTS=(pip split)

# NOTE: loop input via process substitution (not a pipe) and each render gets
# its own stdin (</dev/null) — node/npm otherwise drain the loop's stdin.
while read -r key session id speaker; do
  echo ">>> $speaker  $key"
  if [ ! -f "$HF/assets/$key/meta.json" ]; then
    OC_PROJECT_DIR=$OC/$session $PY $PYDIR/scripts/hf_prep.py "$id" "$HF/assets/$key" </dev/null \
      || { echo "!! prep failed $key"; continue; }
  fi
  for v in "${VARIANTS[@]}"; do
    out="$OUT/${key}_${v}.mp4"
    [ -f "$out" ] && { echo "  skip $(basename "$out")"; continue; }
    $PY $PYDIR/scripts/hf_build.py "assets/$key" "$HF/index.html" "$v" </dev/null >/dev/null \
      || { echo "!! build $key $v"; continue; }
    (cd "$HF" && npm run render >"/tmp/hfr_${key}_${v}.log" 2>&1 </dev/null) \
      || { echo "!! render $key $v (see /tmp/hfr_${key}_${v}.log)"; continue; }
    latest=$(ls -t "$HF"/renders/hf_*.mp4 2>/dev/null | head -1)
    [ -n "$latest" ] && mv "$latest" "$out" && echo "  -> $(basename "$out")"
  done
done < <($PY -c "import json;[print(c['key'],c['session'],c['id'],c['speaker']) for c in json.load(open('$SEL'))]")
echo "=== ANIMATED RENDER DONE: $(ls "$OUT"/*.mp4 2>/dev/null | wc -l | tr -d ' ') reels ==="
