# Organized Cuts — Recordings site

Session viewer for [recordings.organizedai.vip](https://recordings.organizedai.vip):
each session's reels, chapters, transcript, and **interactive widgets** (a
deterministic widget kit in the spirit of [8kEdu](https://github.com/8k-Edu/8kEdu)).
Static — every session is a checked-in JSON file; no backend, no model calls at
view time.

```bash
cd site
npm install
npm run dev        # local dev
npm run build      # -> dist/
npx wrangler deploy  # -> organized-cuts-viewer worker (see wrangler.jsonc)
```

> **Deploy note:** `recordings.organizedai.vip` itself is served by the
> `recordings-organizedai` worker — the paid vault (Stripe auth, R2 video
> streaming). This viewer deploys as a **separate** worker
> (`organized-cuts-viewer`); route a path or subdomain to it rather than
> replacing the vault.

## Layouts

Each viewer picks their layout on the session page; the choice persists in
`localStorage` (`oai.session.layout`):

- **Widgets tab** (default) — player on top; Widgets / Transcript / Chapters tabs below.
- **Companion** — player pinned left, widgets in a live rail beside it, highlighted as playback passes each one.

## Data flow

```
pipeline (jordan-close/scripts)                    site/
  02 analyze  -> analysis/clips.json
  transcript  -> analysis/transcript.json
  03 cut      -> reels/manifest.json
  07 session_data.py  ────────────────────────►  public/sessions/<name>/session.json
        ▲                                        public/sessions/index.json
        └── <project>/widgets.json (hand-authored widget specs, optional)
```

Run per session:

```bash
OC_PROJECT_DIR=../session-x ./.venv/bin/python scripts/07_session_data.py
```

`project.json` extras the viewer understands:

- `title` — display title (defaults to a prettified project name)
- `media_url` — hosted MP4/stream URL for inline playback (optional; without
  it the page still shows chapters, transcript, and widgets)

## Widget specs (`<project>/widgets.json`)

A JSON array. Each spec:

```jsonc
{
  "type": "softmax",          // registry key: softmax | matrix | plot | notebook
  "title": "Softmax & temperature",
  "kind": "concept · softmax",// header eyebrow (optional, defaults to type)
  "caption": "One-line explainer shown above the widget",
  "clip": 1,                  // snap timestamp to this clip's start, or…
  "t": 462.0,                 // …give an explicit time in seconds (wins over clip)
  "props": { }                // type-specific, see below
}
```

| type | props |
|------|-------|
| `softmax` | `labels: string[]`, `logits: number[]`, `tempRange?: [min,max]` — live temperature slider |
| `matrix` | `rows: number[][]`, `rowSoftmax?: bool`, `scaleControl?: {label,min,max,init}` — heatmap; with both extras it's the scaled-dot-product attention view |
| `plot` | `fns: string[]` from `gelu, relu, tanh, sigmoid, silu, sin, cos, exp, log, square`, `xRange?`, `yRange?` — canvas function plot |
| `notebook` | `code: string`, `output: string` — code shown verbatim, ▶ Run reveals the recorded output (deterministic, no client-side eval) |

Unknown types render a labeled fallback instead of crashing, so specs authored
against a newer kit stay safe on an older viewer.

See `public/sessions/demo/session.json` for a complete worked example.
