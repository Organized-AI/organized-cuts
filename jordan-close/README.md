# Jordan Close — Workshop Reel Pipeline

Ingest the Jordan Close talk into TwelveLabs (from a 720p proxy) and cut
short-form 9:16 reels from the frame-synced ProRes masters. ISO1 is the
presenter camera; **ISO2 is a screen-recording of his demo**, not a second angle
on him. So each clip gets one reel: talking-head clips use ISO1 with a
subject-aware crop; demo/reveal clips open on the presenter then cut to the ISO2
screen feed (keeping ISO1 audio). Everything stays local.

## Layout
```
proxy/      720p proxy — TwelveLabs analysis ONLY
analysis/   state.json (index/video/task ids), clips.json (candidates)
reels/      ISO1/ ISO2/ renders, compare/ stills, manifest.json, INDEX.md
scripts/    00..06 numbered pipeline steps + run_all.sh
lib/        common.py (config + helpers)
```

## Inputs (already staged)
- Proxy: `proxy/jordan_close_ISO1_720p.mp4` (analysis only)
- Masters on T7 (final cuts): `..._ISO1.MOV`, `..._ISO2.MOV` (13:04, shared start TC)

## Run
```bash
python3.13 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
# Provide the key: env var, .env file, or:
bash scripts/00_fetch_key.sh          # Infisical (organized-keys)
bash scripts/run_all.sh
```

## Steps
| # | Script | Does |
|---|--------|------|
| 1 | `01_ingest.py` | Create `jordan-close-workshop` index (pegasus1.2 + marengo2.7, thumbnail addon), upload proxy, poll to ready |
| 2 | `02_analyze.py` | Generative highlights+chapters + 5 search queries → merge/de-dupe → `analysis/clips.json` (20–45s, sentence-snapped, hook+caption) |
| 3 | `03_cut_reels.py` | One reel/clip: subject-aware ISO1 crop (face-tracked, 608×1080→1080×1920), demo clips cut to ISO2 screen (fit on blurred backdrop, ISO1 audio), h264_videotoolbox 8000k / aac 160k, +faststart, compare stills, `manifest.json` |
| 4 | `04_pick_angle.py` | QA contact sheet `reels/compare/CONTACT_SHEET.jpg` (person vs. screen per clip) |
| 5 | `05_loudnorm.py` | Loudnorm every reel to -14 LUFS |
| 6 | `06_report.py` | `reels/INDEX.md` + summary table |

**Auth note:** the Infisical CLI is installed at `~/.local/bin/infisical` (and
`/opt/homebrew/bin`). One-time: `infisical login` then `infisical init` (pick
`organized-keys`), then `bash scripts/00_fetch_key.sh`.

Nothing is published; outputs are local. No bucket/Drive is made public.
