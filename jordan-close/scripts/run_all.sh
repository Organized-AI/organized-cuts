#!/usr/bin/env bash
# End-to-end pipeline. Assumes .venv exists and TWELVELABS_API_KEY is resolvable
# (env, .env, or scripts/00_fetch_key.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=./.venv/bin/python

$PY scripts/01_ingest.py
$PY scripts/02_analyze.py
$PY scripts/03_cut_reels.py
$PY scripts/04_pick_angle.py
$PY scripts/05_loudnorm.py
$PY scripts/06_report.py
