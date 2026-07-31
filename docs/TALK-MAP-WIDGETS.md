# Talk Map Widgets

The vault at [recordings.organizedai.vip/vault](https://recordings.organizedai.vip/vault)
already renders a **Talk Map** — a SPINE rail and an ORBIT dial built from
Pegasus chapters, each segment coloured by a category derived from its title,
with a Marengo search box above it. It is fed by two endpoints:

```
GET /api/chapters?video=<key>   ->  {total, chapters:[{start,end,title,summary}]}
GET /api/search?video=<key>&q=  ->  {results:[{t,part,snippet,strong}]}
```

Widgets extend that map rather than replacing it. Stage 07 turns each session's
TwelveLabs analysis into widgets; stage 08 merges them per talk and emits a
payload that is a **superset of what `/api/chapters` already returns**, so the
existing SPINE/ORBIT code keeps working untouched and `widgets` rides alongside.

## Importing the vault's map

The vault is the authority on both halves of this: which recordings belong to
which talk, and what the Talk Map's chapters actually are. Both endpoints are
behind the member login (`401` without a session cookie), so `import_talkmap.py`
takes an export rather than calling them.

From a logged-in tab on the vault, in the console:

```js
copy(await (async () => {
  const {videos} = await (await fetch("/api/videos")).json();
  const chapters = {};
  for (const v of videos)
    chapters[v.key] = await (await fetch(
      "/api/chapters?video=" + encodeURIComponent(v.key))).json();
  return JSON.stringify({videos, chapters}, null, 2);
})())
```

Then:

```bash
./.venv/bin/python scripts/import_talkmap.py vault-export.json           # report only
./.venv/bin/python scripts/import_talkmap.py vault-export.json --write   # apply
```

It reconciles the vault's recordings against the registry — a recording's key
starts with its talk id (`01 …`), which is how the vault itself selects a talk —
and writes each session's `analysis/chapters.json` from the vault's chapters. So
07 builds widgets on the map that is already live rather than asking Pegasus for
a second, slightly different opinion.

Where a talk's recording count and session count agree they are paired in order.
Where they disagree the importer refuses that talk, says so, and exits non-zero;
pair them explicitly with `--map "01 Michael part2.mp4=session-4a-michael"` or fix
the registry. **This is what settles the open mapping questions** — the registry
in this repo is a best guess from directory names until an export confirms it.

## Pipeline

```
07 widgets     per session: TwelveLabs analysis -> analysis/widgets.json
08 talkmap     all sessions: merge per talk     -> talkmap/build/
```

```bash
# one session
OC_PROJECT_DIR=../session-2-ct ./.venv/bin/python scripts/07_widgets.py

# every session in the registry, then merge
bash scripts/widgets_all.sh
bash scripts/widgets_all.sh --offline     # no API calls, local artifacts only

# checks, no key required
python3 tests/test_widgets.py
```

## Where each widget comes from

Every widget traces to something TwelveLabs indexed, analyzed, or determined for
that asset. The `source` field carries the provenance verbatim.

| Widget | TwelveLabs signal | `source` |
|---|---|---|
| `chapter_map` | Pegasus chapters — the map spine, with categories + legend | `twelvelabs:pegasus.chapters` |
| `qa_index` | chapters that classify as Q&A, rolled into one index | `twelvelabs:pegasus.chapters` |
| `moment` | a Pegasus highlight, linked to its cut reel when one exists | `twelvelabs:pegasus.highlight` |
| `demo_walkthrough` | a clip classified `kind=demo` (cuts to the ISO2 screen feed) | `twelvelabs:marengo.search` / `pegasus.*` |
| `quote` | top Marengo hits for *quotable one-liner* | `twelvelabs:marengo.search` |
| `takeaway` | top Marengo hits for *actionable takeaway builders can use* | `twelvelabs:marengo.search` |
| `search_probe` | nine pre-baked Marengo queries with their hit timecodes | `twelvelabs:marengo.search` |
| `topic_index` | Pegasus gist — topics + hashtags for the whole asset | `twelvelabs:pegasus.gist` |
| `reel_strip` | the reels this pipeline cut from the talk | `organized-cuts:reels/manifest.json` |
| `cross_talk` | a topic this talk shares with another speaker's talk | `organized-cuts:topic-index` |

The first five `search_probe` queries are the pipeline's own clip-finding queries
from `02_analyze.py`, so the widget surfaces exactly what the reels were chosen
from. The remaining four are the questions audiences ask of a recording (cost,
tooling, audience questions, gotchas).

## Widget shape

```json
{
  "id": "t03_session-2-ct_demo_04",
  "type": "demo_walkthrough",
  "talk": "03",
  "session": "session-2-ct",
  "title": "Watch the router pick Haiku",
  "category": "demo",
  "color": "#f5d623",
  "start": 812.5, "end": 848.0, "duration": 35.5,
  "t_label": "13:32",
  "source": "twelvelabs:marengo.search",
  "confidence": 0.91,
  "body": { "...": "type-specific" },
  "actions": [{ "kind": "seek", "t": 812.5 }]
}
```

`category` and `color` come from the same six categories the vault uses — same
ids, same regexes, same hex values (`lib/talkmap.py: CATEGORIES` mirrors the
site's `TLCATS`). Change them in one place and the other must follow, or the map
re-colours itself.

`actions` is what the surface can do with the widget: `seek` jumps the player,
`search` hands a query to `/api/search`.

## Categories

| id | label | colour |
|---|---|---|
| `intro` | Intro / Wrap | `#9a927f` |
| `qa` | Q&A | `#b48ead` |
| `data` | Data / Tokens | `#e0985a` |
| `demo` | Live Demo | `#f5d623` |
| `tools` | Tools / Platform | `#90b97e` |
| `concept` | Concepts | `#7aa2c9` |

Classification is title-first, summary as fallback, `concept` catches the rest —
identical precedence to the vault.

## The registry

[`talks/registry.json`](../talks/registry.json) is the one place sessions are
mapped to the talks on the site. `id` is the `?talk=` id the vault uses.

| Talk | Speaker | Title | Sessions |
|---|---|---|---|
| 01 | Michael | Real-Time Web Data for Agents | `session-4-michael`, `session-4a-michael`, `session-5-michael`, `session-5a-michael` |
| 02 | Esteban | Mastering Harness Engineering | `session-1-esteban` |
| 03 | CT | Tokenomics | `session-2-ct` |
| 04 | Rohit | Local AI, Without the Cloud | `session-3-rohit`, `session-3a-rohit` |
| 05 | Jordaaan | Observability | `studio-jordan` |
| 06 | Shep | Build Your Second Brain | `session-6-shep`, `session-6a-shep` |
| 07 | Henry | Mastering AI Loops | *(no footage in this repo)* |

A session belongs to **exactly one** talk; `load_registry()` raises if two talks
claim the same one. `jordan-close/` is the reference pipeline project, not a Vol 2
talk, so it is deliberately absent.

### Multi-part talks

A talk recorded across several sessions is stitched onto one timeline: part 2's
timecodes are offset by part 1's runtime, and so on in `sessions` order. Widget
`start`/`end`, seek actions, and nested `segments`/`items`/`hits`/`reels` all
shift together. Reorder `sessions` and the offsets follow — so the list order is
the running order of the recording, not a preference.

## Build output

```
talkmap/build/
  talkmap.json        every talk + widget, one document
  talks/<id>.json     per talk: {talk, speaker, title, total, chapters, widgets}
  index.html          self-contained preview of every map + widget
```

`talks/<id>.json` is the vault-compatible one. `{total, chapters}` is byte-for-byte
what the SPINE/ORBIT renderer consumes today; serving these files (or copying the
`widgets` array into the existing `/api/chapters` response) is an additive change.
Chapters additionally carry `category`, `color`, and `session`, which the current
renderer ignores — it derives category client-side — but which let the site drop
that regex work and trust the pipeline instead.

The build dir is gitignored: it is generated from client content. Only the
registry, the code, and this doc are committed.

## Caching and cost

Stage 07 caches every network response next to the analysis it came from:

```
analysis/chapters.json    Pegasus chapters
analysis/topics.json      Pegasus gist (topics + hashtags)
analysis/probes.json      Marengo hits per probe query
analysis/widgets.json     the built widgets
```

Re-runs read the cache and cost nothing. `--refresh` drops the caches and
re-fetches; `--offline` never calls the API and builds from whatever is on disk.

If you already have chapters from the vault's own `/api/chapters`, drop them into
`analysis/chapters.json` as `{"chapters": [...]}` and stage 07 will use those
verbatim rather than asking Pegasus for a second opinion — which is the point of
"connect it to the *existing* Talk Map".

## Running without the masters

Stages 07 and 08 **never open a video file** — not the ProRes masters on the T7,
not the 720p proxy. Only `03_cut_reels.py`, `prepare_media.py`,
`demo_candidates.py` and `hf_prep.py` touch `MASTERS`. The widget stages need the
TwelveLabs index (already analyzed) plus local analysis JSON, so they run on any
machine with the API key — no drive attached.

What each input costs you if it is absent:

| Missing | Effect | Fix, no media needed |
|---|---|---|
| `analysis/state.json` | can't reach the index | automatic — 07 resolves index + video by `index_name` from `project.json` and writes state.json back |
| `analysis/chapters.json` | no `chapter_map`, no `qa_index` | 07 asks Pegasus, or paste the vault's own `/api/chapters` response in |
| `analysis/clips.json` | no `moment`, `demo_walkthrough`, `quote`, `takeaway` | re-run `02_analyze.py` — it is pure API (its transcript comes from the index) |
| `reels/manifest.json` | no `reel_strip`; `moment.reel` is null | needs cut reels, so this one does want the masters |

So on a machine with just the key and the registry:

```bash
OC_PROJECT_DIR=../session-2-ct ./.venv/bin/python scripts/02_analyze.py   # if no clips.json
OC_PROJECT_DIR=../session-2-ct ./.venv/bin/python scripts/07_widgets.py
```

`reel_strip` is the only widget type that genuinely depends on the ProRes
masters, because it lists reels this pipeline rendered. To get reels without the
T7 at all, add `masters_url` to `project.json` pointing at the hosted copies —
see [Masters without the drive](../jordan-close/README.md#masters-without-the-drive).
A local master still wins when the drive is attached, so the setting is safe to
leave in place permanently.

## Transcription fixes

ASR reliably mangles a handful of names across these talks (`Appify` → `Apify`,
`Cloud Code` → `Claude Code`, `Quinn` → `Qwen`, `Light Alarm` → `LiteLLM`,
`Lang fuse` → `Langfuse`). The vault patches chapter text client-side; stage 07
patches every string a widget carries, so the fix travels with the data instead
of being re-applied on each surface.
