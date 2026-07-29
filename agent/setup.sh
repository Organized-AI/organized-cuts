#!/usr/bin/env bash
# One-time setup for the agent corpus stack: a private venv with the MCP SDK
# (macOS system/Homebrew Python is "externally managed", so a bare
# `pip install mcp` fails there — the venv sidesteps that everywhere).
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt
echo "✓ agent/.venv ready — run_server.sh and test_agent.py will use it automatically"
