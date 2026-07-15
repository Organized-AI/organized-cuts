# event-vertical — Single-Cam DJI Reels

Vertical (9:16) reels cut from a **single continuous DJI recording**. The camera
auto-splits the take into numbered segments (`DJI_<ts>_<seq>_D.MP4`); this project
joins them into one ISO1 master, then runs the standard Organized Cuts pipeline.

There is **no ISO2** (no screen feed / second angle), so every reel is a
subject-aware talking-head crop — the demo picture-in-picture path is skipped
automatically (`common.py: ISO2_PRESENT` is false).

> Rename this folder / `name` / `index_name` to your real event once you pick one.

## 0. Get the footage local
Download the 28 `DJI_*.MP4` files from the Drive folder to your Mac (they total
~33 GB — too big to process in the cloud), e.g. into
`/Volumes/T7/Vol 2 Workshop/Event/DJI/`.

## 1. Point `project.json` at it
Edit these two absolute paths:
- `dji_source` — the folder holding the `DJI_*.MP4` segments.
- `masters.ISO1` — where the joined master should be written.

(`caption_color` is RGB, per-speaker; `upload_folder` is the Drive destination.)

## 2. Run (from `jordan-close/`)
```bash
cd jordan-close
python3.13 -m venv .venv && ./.venv/bin/pip install -r requirements.txt   # once
export OC_PROJECT_DIR=../event-vertical
export PATH="$HOME/.local/bin:$PATH"
PY=./.venv/bin/python

$PY scripts/prepare_dji.py        # join 28 segments → one ISO1 master (lossless)
$PY scripts/prepare_media.py      # 720p proxy (TwelveLabs) + 16k mono audio (Whisper)
$PY scripts/01_ingest.py          # create index, upload proxy, poll to ready
$PY scripts/whisper_transcript.py # word-accurate transcript
$PY scripts/02_analyze.py         # highlights + search → analysis/clips.json
$PY scripts/03_cut_reels.py       # cut 9:16 reels (ISO1 subject-aware crop + captions)
$PY scripts/05_loudnorm.py        # normalize to -14 LUFS
$PY scripts/06_report.py          # reels/INDEX.md
```

`prepare_dji.py` is idempotent — it skips the join if the master already exists.
The rest of the pipeline is the shared jordan-close code, unchanged.

## Notes
- **Concat is lossless** (`-c copy`). If the segments' codecs differ and it
  fails, `prepare_dji.py` prints a ready-to-run re-encode fallback command.
- Nothing is uploaded until you run the rclone step yourself (see
  `scripts/run_session.sh` for the staging + `rclone copy` pattern).
- Needs `ffmpeg` and a TwelveLabs API key — neither is available in the cloud
  session, so run this locally.
