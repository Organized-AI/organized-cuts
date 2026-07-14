#!/usr/bin/env python3
"""05 — Loudness-normalise every rendered reel in place (both angles).

Single-pass EBU R128 loudnorm to -14 LUFS (social standard). Video is copied,
only audio is re-encoded, so this is fast and lossless for the picture.

    ./.venv/bin/python scripts/05_loudnorm.py
"""
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C

LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"


def normalize(path: pathlib.Path):
    tmp = path.with_suffix(".norm.mp4")
    p = subprocess.run([
        "ffmpeg", "-y", "-i", str(path),
        "-c:v", "copy", "-af", LOUDNORM, "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(tmp),
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-6:])
        raise RuntimeError(f"loudnorm failed for {path.name}:\n{tail}")
    tmp.replace(path)


def main():
    argv = sys.argv[1:]
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None
    reels = sorted(C.REEL_OUT.glob("reel_*.mp4"))
    if only:
        reels = [r for r in reels if r.stem.replace("reel_", "") in only]
    if not reels:
        C.die("No reels found. Run scripts/03_cut_reels.py first.")
    for r in reels:
        normalize(r)
        print(f"  ✓ {r.relative_to(C.ROOT)}")
    print(f"\n✓ Normalised {len(reels)} reels to -14 LUFS.")


if __name__ == "__main__":
    main()
