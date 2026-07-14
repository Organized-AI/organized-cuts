#!/usr/bin/env bash
# Fetch TWELVELABS_API_KEY from Infisical (project: organized-keys) into .env.
# Requires a working `infisical` CLI that is already authenticated
# (infisical login, or INFISICAL_TOKEN / machine-identity env vars).
set -euo pipefail
cd "$(dirname "$0")/.."

INFISICAL="$(command -v infisical || echo "$HOME/.local/bin/infisical")"
if [ ! -x "$INFISICAL" ]; then
  echo "infisical CLI not found on PATH." >&2
  echo "Install it, or paste the key into .env manually (see .env.example)." >&2
  exit 1
fi

# One-time per machine:  infisical login   (interactive, opens a browser)
# One-time per project:  infisical init    (link this dir to the 'organized-keys' project)
# then this script can read secrets non-interactively.
alias() { :; }; alias infisical="$INFISICAL"  # noop guard for older bash
infisical() { "$INFISICAL" "$@"; }

VAL="$(infisical secrets get TWELVELABS_API_KEY \
        --projectId "${INFISICAL_PROJECT_ID:-}" \
        --env "${INFISICAL_ENV:-prod}" \
        --plain 2>/dev/null || true)"

if [ -z "${VAL:-}" ]; then
  # Fall back to name-based lookup without projectId (uses local .infisical.json)
  VAL="$(infisical secrets get TWELVELABS_API_KEY --plain 2>/dev/null || true)"
fi

if [ -z "${VAL:-}" ]; then
  echo "Could not read TWELVELABS_API_KEY from Infisical." >&2
  echo "Check auth (infisical login) and project selection (organized-keys)." >&2
  exit 1
fi

grep -v '^TWELVELABS_API_KEY=' .env 2>/dev/null > .env.tmp || true
echo "TWELVELABS_API_KEY=${VAL}" >> .env.tmp
mv .env.tmp .env
echo "✓ Wrote TWELVELABS_API_KEY to .env"
