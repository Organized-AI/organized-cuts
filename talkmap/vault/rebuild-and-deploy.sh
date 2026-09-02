#!/usr/bin/env bash
# Rebuild the vault's wrangler project from what is live, then deploy the new page.
# For when the original project directory cannot be found.
#
#   bash talkmap/vault/rebuild-and-deploy.sh                 # -> ~/recordings-organizedai, deploy
#   DRY=1 bash talkmap/vault/rebuild-and-deploy.sh           # build everything, stop before deploy
#   bash talkmap/vault/rebuild-and-deploy.sh /other/dir      # choose the project dir
#
# What it does, and why each step is safe:
#   1. `wrangler init --from-dash recordings-organizedai` — Cloudflare's CLI downloads
#      the Worker's live script. Nothing is invented; this is the code running now.
#   2. Writes wrangler.toml with the bindings the script uses, resolved from the
#      account (not guessed): KV recordings-organizedai-VAULT and R2 vol2-recordings.
#      No `routes` key, so the recordings.organizedai.vip domain is left exactly as is.
#   3. Rebuilds the assets directory by fetching every static file the live pages
#      reference, then drops in the new vault.html.
#   4. `wrangler deploy --keep-vars` — secrets persist across deploys anyway;
#      --keep-vars also keeps plain vars like VAULT_PAYMENT_LINKS.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER=recordings-organizedai
SITE=https://recordings.organizedai.vip
PROJ="${1:-$HOME/$WORKER}"
KV_ID=077b2f50bd704953a76ba71cd219c00d          # recordings-organizedai-VAULT
R2_BUCKET=vol2-recordings

say(){ printf '• %s\n' "$*"; }
die(){ printf '!! %s\n' "$*" >&2; exit 1; }

# ---- 1. the live script -------------------------------------------------------
if [ -d "$PROJ" ] && find "$PROJ" -maxdepth 3 -type f \( -name '*.js' -o -name '*.mjs' -o -name '*.ts' \) -not -path '*/node_modules/*' -print0 2>/dev/null | xargs -0 grep -lq vol2_recordings 2>/dev/null; then
  say "worker script already present in $PROJ — not re-downloading"
else
  mkdir -p "$(dirname "$PROJ")"
  # a half-finished earlier run leaves a dir with no script; init refuses to write into it
  if [ -d "$PROJ" ]; then mv "$PROJ" "$PROJ.partial.$(date +%Y%m%d%H%M%S)"; say "moved an empty $PROJ aside"; fi
  say "downloading the live Worker with wrangler init --from-dash $WORKER"
  ( cd "$(dirname "$PROJ")" && npx wrangler init "$(basename "$PROJ")" --from-dash "$WORKER" --yes ) \
    || die "wrangler init --from-dash failed. Run 'npx wrangler login' first if you are not signed in."
fi
MAIN="$(cd "$PROJ" && find . -maxdepth 3 -type f \( -name '*.js' -o -name '*.mjs' -o -name '*.ts' \) -not -path '*/node_modules/*' -print0 | xargs -0 grep -l vol2_recordings | head -1 | sed 's#^\./##')"
[ -n "$MAIN" ] || die "no downloaded file mentions vol2_recordings — this is not the vault Worker"
say "worker entry: $MAIN"

# ---- 2. a config we can vouch for ---------------------------------------------
cd "$PROJ"
COMPAT="$( { grep -hoE 'compatibility_date"?\s*[=:]\s*"[0-9-]+"' wrangler.toml wrangler.json wrangler.jsonc 2>/dev/null || true; } | head -1 | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' || echo 2026-07-17)"
for f in wrangler.toml wrangler.json wrangler.jsonc; do [ -f "$f" ] && mv "$f" "$f.from-dash.$(date +%Y%m%d%H%M%S)"; done
cat > wrangler.toml <<TOML
name = "$WORKER"
main = "$MAIN"
compatibility_date = "$COMPAT"

[assets]
directory = "./public"
binding = "ASSETS"

[[kv_namespaces]]
binding = "VAULT"
id = "$KV_ID"

[[r2_buckets]]
binding = "vol2_recordings"
bucket_name = "$R2_BUCKET"
TOML
say "wrote wrangler.toml (compatibility_date $COMPAT; previous config kept alongside)"

# ---- 3. the static assets, from the live site ---------------------------------
rm -rf public && mkdir -p public
crawl(){ # print same-origin static paths referenced by a live page
  curl -sf --max-time 30 "$SITE$1" \
  | grep -oE '(src|href|poster|url\()=?["'"'"'(]?[^"'"'"' )>]+' \
  | sed -E 's/^(src|href|poster)=["'"'"']?//; s/^url\(["'"'"']?//' \
  | sed -E "s#^$SITE##" \
  | grep -E '^(/|assets/|[a-z0-9_-]+\.(png|jpg|jpeg|svg|webp|ico|css|js|txt|mp4|webm))' \
  | grep -vE '^//|^/(api|media|promo|buy|claim|vault|#|$)' \
  | sed -E 's#^([^/])#/\1#' | sort -u
}
for p in / /vault; do curl -sf --max-time 30 "$SITE$p" -o "public/$( [ "$p" = / ] && echo index.html || echo "${p#/}.html")"; done
{ crawl /; crawl /vault; echo /robots.txt; echo /assets/icon.png; } | sort -u > .assets.txt
while read -r a; do
  mkdir -p "public/$(dirname "$a")"
  if curl -sf --max-time 60 "$SITE$a" -o "public$a"; then printf '  %-42s %s\n' "$a" "$(wc -c <"public$a") bytes"; else printf '  %-42s (not fetched)\n' "$a"; rm -f "public$a"; fi
done < .assets.txt
cp "$HERE/vault.html" public/vault.html
grep -q 'data-view="longcut"' public/vault.html && say "public/vault.html is the new page (SESSIONS / LONG CUT present)"
say "assets: $(find public -type f | wc -l | tr -d ' ') files in $PROJ/public"

# ---- 4. deploy ------------------------------------------------------------------
[ "${DRY:-}" = "1" ] && { say "DRY=1 — stopping before deploy. Inspect $PROJ then rerun without DRY."; exit 0; }
say "npx wrangler deploy --keep-vars"
npx wrangler deploy --keep-vars
cat <<'SMOKE'

✓ deployed. Signed in at recordings.organizedai.vip/vault, check:
  1. landing page at / still renders with the speaker cards
  2. SESSIONS unchanged; sign-in still works (KV binding intact)
  3. LONG CUT: 7 talks · 145 chapters · 3h 52m; a talk plays (R2 binding intact)
  4. let talk 01 end -> continues into 02 Esteban, not 03
SMOKE
