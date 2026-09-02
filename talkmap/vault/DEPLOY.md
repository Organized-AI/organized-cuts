# Deploying the vault page

The site is the Cloudflare Worker **`recordings-organizedai`**. Its script
handles `/api/*`, `/media/*`, Stripe and passkeys; everything else falls
through to `env.ASSETS.fetch(request)`. So `/vault` — the page in this
directory — is a **static asset bundled with the Worker**, and deploying it
means redeploying the Worker with the updated asset in place.

## What ships

| File | Goes to | Purpose |
|---|---|---|
| `vault.html` | the project's assets dir, replacing the existing `vault.html` | the vault with the SESSIONS / LONG CUT switch |
| `continuous.html` | optional, e.g. `longcut.html` in the same dir | the long cut as a standalone page |

`tlcats.js` is reference only — its contents are already inside `vault.html`.

## Do it from the existing project, not a fresh one

Workers Assets replaces the **entire** asset set on every deploy. Deploying
from a directory that contains only `vault.html` would remove the landing
page at `/`, `/assets/*.jpg`, `icon.png` and anything else the site serves.

```bash
cd <the recordings-organizedai wrangler project>       # has wrangler.toml with [assets]
cp <organized-cuts>/talkmap/vault/vault.html <assets dir>/vault.html
npx wrangler deploy
```

The assets directory is whatever `[assets] directory = ...` names in that
project's `wrangler.toml`. If the page is served as `vault/index.html` rather
than `vault.html`, mirror that.

## Smoke test after deploy (signed in)

1. **SESSIONS is unchanged** — talk list, per-talk map, search all behave as before.
2. **LONG CUT loads** — stats read 7 talks · 145 chapters · 3h 52m; the rail shows
   seven speaker boundaries.
3. **Seek across a boundary** — click the rail just past the CT boundary. The
   player should swap to talk 03 and land ~1 minute in, not restart at 0.
4. **Roll-over** — scrub to the last 10 s of talk 01 and let it end. It must
   continue into **02 (Esteban)**, not skip to 03. (This was a real bug; fixed.)
5. **A thread hops speakers** — pick *Cost & tokens*. The second moment is
   Esteban's; the source should swap and land at 28:08 (1688 s).
6. **Switch back** — SESSIONS should show the same recording at the same second.

If step 3 stalls at 0 s the seek happened before `loadedmetadata`; the page
waits for that event, so this would point at a `Range` problem on `/media`
rather than the page.

## Confirmed from the Worker source, not assumed

- `/media/<key>` serves R2 with `206`, `Content-Range` and `Accept-Ranges: bytes`,
  so `currentTime` seeks are honoured.
- Auth is an HttpOnly `vault_session` cookie, `SameSite=Lax`, checked on
  `/media` — a same-origin `<video>` sends it; nothing off-origin can play.
- `/api/videos` → `{videos:[{key,title,size}]}`; `/api/chapters` →
  `{total, chapters:[{start,end,title,summary,part}]}`. Both consumed as-is.

## One optional follow-up in the Worker itself

`/api/search`'s server-side `fixSnip` still lacks the two ASR fixes added to
the page (`QIN` → Qwen, `LightLM` → LiteLLM). It only affects search snippets.
To match, extend that chain in `worker.js`:

```js
.replace(/\bQIN\b/g,"Qwen").replace(/\bLightLM\b/g,"LiteLLM")
```
