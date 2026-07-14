#!/usr/bin/env bash
# Run every remaining session through the pipeline, continuing on failure.
set -uo pipefail
OC=/Users/supabowl/organized-cuts
SESSIONS=(
  # Shep sessions (6, 6A) skipped for now per request
  session-3a-rohit
  session-5a-michael
  session-5-michael
  session-4a-michael
  session-4-michael
  session-2-ct
  session-1-esteban    # biggest (51 min) last
)
FAIL=()
for s in "${SESSIONS[@]}"; do
  echo ">>>>>>>>>> START $s  $(date +%H:%M:%S)"
  if bash /Users/supabowl/organized-cuts/jordan-close/scripts/run_session.sh "$OC/$s"; then
    echo ">>>>>>>>>> OK $s"
  else
    echo ">>>>>>>>>> FAILED $s"; FAIL+=("$s")
  fi
done
echo "=================================="
echo "BATCH COMPLETE. Failures: ${FAIL[*]:-none}"
