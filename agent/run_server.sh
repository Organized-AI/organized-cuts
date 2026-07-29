#!/usr/bin/env bash
# Launch the corpus MCP server with the right interpreter:
# agent/.venv if it exists (created by agent/setup.sh), else system python3.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"
[ -x "$PY" ] || PY=python3
exec "$PY" "$DIR/server.py"
