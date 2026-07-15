#!/usr/bin/env bash
# Add long-form (0:45–1:30) reels to every branded session folder, continuing on
# failure. Each session must already have its short reels done (needs its
# analysis/state.json + transcript.json); run_long.sh skips ingest/whisper.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # jordan-close/
OC="$(cd "$HERE/.." && pwd)"                              # repo root
SESSIONS=(
  jordan-close
  studio-jordan
  session-1-esteban
  session-2-ct
  session-3-rohit
  session-3a-rohit
  session-4-michael
  session-4a-michael
  session-5-michael
  session-5a-michael
  session-6-shep
  session-6a-shep
  # henry: excluded until it's ingested (no short run yet)
  # animated: hyperframes project, not a talk
)
FAIL=()
for s in "${SESSIONS[@]}"; do
  echo ">>>>>>>>>> START $s (long)  $(date +%H:%M:%S)"
  DIR="$OC/$s"; [ "$s" = "jordan-close" ] && DIR="$HERE"
  if bash "$HERE/scripts/run_long.sh" "$DIR"; then
    echo ">>>>>>>>>> OK $s"
  else
    echo ">>>>>>>>>> FAILED $s"; FAIL+=("$s")
  fi
done
echo "=================================="
echo "BATCH (long) COMPLETE. Failures: ${FAIL[*]:-none}"
