#!/usr/bin/env bash
# Put the updated vault page into the wrangler project and deploy it.
#
#   bash talkmap/vault/deploy.sh /path/to/recordings-organizedai        # deploy
#   DRY=1 bash talkmap/vault/deploy.sh /path/to/recordings-organizedai  # stage only
#
# Runs FROM YOUR EXISTING PROJECT on purpose: Workers Assets replaces the whole
# asset set on every deploy, so this never invents a project of its own — it
# reads the assets directory out of your wrangler config, swaps one file, and
# hands off to wrangler. Your bindings, secrets and other assets are untouched.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ="${1:?usage: deploy.sh <wrangler project dir>}"
PROJ="$(cd "$PROJ" && pwd)"

CFG=""
for c in wrangler.toml wrangler.jsonc wrangler.json; do
  [ -f "$PROJ/$c" ] && { CFG="$PROJ/$c"; break; }
done
[ -n "$CFG" ] || { echo "!! no wrangler config in $PROJ"; exit 1; }
grep -q "recordings-organizedai" "$CFG" || echo "?? $CFG does not name recordings-organizedai — check you have the right project"

# assets directory from the config; fall back to the usual suspects
ASSETS="$(grep -E '^\s*(directory|"directory")\s*[=:]' "$CFG" | head -1 | sed -E 's/.*[=:]\s*"([^"]+)".*/\1/' || true)"
if [ -z "$ASSETS" ]; then
  for d in public assets site dist static; do [ -d "$PROJ/$d" ] && { ASSETS="$d"; break; }; done
fi
[ -n "$ASSETS" ] && [ -d "$PROJ/$ASSETS" ] || { echo "!! could not find the assets directory (looked in $CFG)"; exit 1; }
ADIR="$PROJ/$ASSETS"

# the page is served at /vault — honour whichever layout the project already uses
if   [ -f "$ADIR/vault/index.html" ]; then DEST="$ADIR/vault/index.html"
elif [ -f "$ADIR/vault.html" ];       then DEST="$ADIR/vault.html"
else echo "!! neither $ASSETS/vault.html nor $ASSETS/vault/index.html exists — is this the vault project?"; exit 1; fi

cp "$DEST" "$DEST.bak.$(date +%Y%m%d%H%M%S)"
cp "$HERE/vault.html" "$DEST"
echo "• staged $(basename "$HERE")/vault.html -> ${DEST#$PROJ/}   (backup alongside)"
grep -q 'data-view="longcut"' "$DEST" && echo "• SESSIONS / LONG CUT switch present"

if [ "${DRY:-}" = "1" ]; then echo "• DRY=1 — not deploying"; exit 0; fi
cd "$PROJ"
echo "• npx wrangler deploy"
npx wrangler deploy
cat <<'SMOKE'

✓ deployed. Signed in at recordings.organizedai.vip/vault, check:
  1. SESSIONS unchanged     2. LONG CUT: 7 talks · 145 chapters · 3h 52m
  3. seek past the CT boundary -> talk 03, ~1 min in (not 0:00)
  4. let talk 01 end -> continues into 02 Esteban (not 03)
  5. Cost & tokens thread -> 2nd moment swaps to Esteban at 28:08
SMOKE
