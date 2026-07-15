# henry — Henry's Talk (Single-Cam DJI Reels)

Vertical (9:16) reels from **Henry's ~30-minute talk**, captured single-cam on
DJI. The camera auto-split the take into three contiguous segments; this project
joins just those, then runs the standard Organized Cuts pipeline.

| Segment | File | ~Start | ~Size | Role |
|---------|------|--------|-------|------|
| 149 | `DJI_20000428060110_0149_D.MP4` | 06:01:10 | 163 MB | intro / lead-in (~72 s) |
| 150 | `DJI_20000428060222_0150_D.MP4` | 06:02:22 | 17 GB  | main talk (~21 min) |
| 151 | `DJI_20000428062349_0151_D.MP4` | 06:23:49 | 5.8 GB | tail / Q&A (~7 min) |

Single camera, **no ISO2** — every reel is a subject-aware talking-head crop
(the demo picture-in-picture path is skipped automatically).

## 0. Get the footage local
Download the three segments above from the Drive folder to your Mac, e.g. into
`/Volumes/T7/Vol 2 Workshop/Event/DJI/`. (They total ~23 GB — too big for the
cloud session; `prepare_dji.py` joins only the three listed in `dji_segments`.)

## 1. Check `project.json`
- `dji_source` — the folder holding the `DJI_*.MP4` segments.
- `dji_segments` — `[149, 150, 151]` (joined in this order). Drop 149/151 if you
  only want the main talk body.
- `masters.ISO1` — where the joined master is written.

## 2. Run (from `jordan-close/`)
```bash
cd jordan-close
python3.13 -m venv .venv && ./.venv/bin/pip install -r requirements.txt   # once
export OC_PROJECT_DIR=../henry
export PATH="$HOME/.local/bin:$PATH"
PY=./.venv/bin/python

$PY scripts/prepare_dji.py        # join segments 149,150,151 → one ISO1 master (lossless)
$PY scripts/prepare_media.py      # 720p proxy (TwelveLabs) + 16k mono audio (Whisper)
$PY scripts/01_ingest.py          # create henry-talk index, upload proxy, poll ready
$PY scripts/whisper_transcript.py # word-accurate transcript
$PY scripts/02_analyze.py         # TwelveLabs highlights + search → analysis/clips.json
$PY scripts/03_cut_reels.py       # cut 9:16 reels (ISO1 subject-aware crop + captions)
$PY scripts/05_loudnorm.py        # normalize to -14 LUFS
$PY scripts/06_report.py          # reels/INDEX.md — review the picks here
```

`02_analyze.py` is where the "which moments to clip" decision happens
(TwelveLabs Pegasus highlights + Marengo search). Review `analysis/clips.json`
before cutting if you want to hand-tune the picks.

## Notes
- **Concat is lossless** (`-c copy`). If the segments' codecs differ and it
  fails, `prepare_dji.py` prints a re-encode fallback command.
- Needs `ffmpeg` + a TwelveLabs API key — run locally, not in the cloud session.
- Nothing uploads until you run the rclone step (see `scripts/run_session.sh`).
