#!/usr/bin/env python3
"""Concatenate DJI auto-split segments into a single ISO1 master.

DJI cameras roll continuously but write the recording as a sequence of numbered
segments (DJI_<ts>_<seq>_D.MP4). The reel pipeline expects ONE master file per
angle, so this step losslessly joins the segments (stream copy — fast, no
re-encode) into the project's ISO1 master before prepare_media / ingest run.

Config (project.json):
    dji_source   directory holding the DJI_*.MP4 segments (absolute path)
    masters.ISO1 absolute path to write the joined master to

    OC_PROJECT_DIR=../event-vertical ./.venv/bin/python scripts/prepare_dji.py
"""
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C


def segments(src: pathlib.Path) -> list[pathlib.Path]:
    """DJI_*.MP4 segments, ordered. The timestamp+sequence in the filename is
    chronological, so a plain lexical sort is the recording order."""
    files = [p for p in src.iterdir()
             if p.is_file() and p.suffix.lower() == ".mp4" and p.name.upper().startswith("DJI_")]
    return sorted(files, key=lambda p: p.name)


def main():
    src = C.CFG.get("dji_source")
    if not src:
        C.die("project.json is missing 'dji_source' (folder of DJI_*.MP4 segments).")
    src = pathlib.Path(src)
    if not src.is_dir():
        C.die(f"dji_source not found or not a directory: {src}")

    out = C.MASTERS.get("ISO1")
    if not out:
        C.die("project.json masters.ISO1 is not set (target path for the joined master).")
    out = pathlib.Path(out)

    if out.exists():
        print(f"• master exists: {out} ({out.stat().st_size/1e9:.1f} GB) — skipping concat")
        return

    segs = segments(src)
    if not segs:
        C.die(f"No DJI_*.MP4 segments found in {src}")
    total = sum(p.stat().st_size for p in segs)
    print(f"• joining {len(segs)} segments ({total/1e9:.1f} GB) → {out}")
    print(f"    first: {segs[0].name}")
    print(f"    last:  {segs[-1].name}")

    out.parent.mkdir(parents=True, exist_ok=True)
    # ffmpeg concat demuxer needs a list file; single-quote paths per its syntax.
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in segs:
            f.write(f"file '{p.resolve().as_posix()}'\n")
        listfile = f.name

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
             "-c", "copy", "-movflags", "+faststart", str(out)],
            check=True,
        )
    except subprocess.CalledProcessError:
        C.die(
            "Lossless concat failed — the segments' codecs/params may differ.\n"
            "  Re-run this join with a re-encode instead, e.g.:\n"
            f"    ffmpeg -f concat -safe 0 -i {listfile} \\\n"
            "      -c:v h264_videotoolbox -b:v 12000k -c:a aac -b:a 192k \\\n"
            "      -movflags +faststart '" + str(out) + "'"
        )
    finally:
        pathlib.Path(listfile).unlink(missing_ok=True)

    print(f"✓ master={out.name} ({out.stat().st_size/1e9:.1f} GB)")


if __name__ == "__main__":
    main()
