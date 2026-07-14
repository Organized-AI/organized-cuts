#!/usr/bin/env python3
"""Prepare Hyperframes assets for one demo clip: cut reframed video segments +
dump caption cues + meta. Reuses the manifest's crop and the project's colour.

    OC_PROJECT_DIR=../session-x ./.venv/bin/python scripts/hf_prep.py <clip_id> <out_dir>
"""
import json
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C
from lib import captions as CAP

SCREEN_FIT = ("split=2[sbg][sfg];"
              "[sbg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[sbgb];"
              "[sfg]scale=1080:-2[sfgs];[sbgb][sfgs]overlay=(W-w)/2:(H-h)/2,setsar=1")
ENC = ["-c:v", "h264_videotoolbox", "-b:v", "9000k", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]
PAD = 0.3


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError("\n".join(p.stderr.strip().splitlines()[-6:]))


def main():
    cid, out = sys.argv[1], pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    man = json.loads(C.MANIFEST_PATH.read_text())
    clip = next(c for c in man["clips"] if c["id"] == cid)
    s0 = max(0.0, clip["start"] - PAD)
    dur = (clip["end"] + PAD) - s0
    x0 = clip.get("crop_x0", int(C.DEFAULT_CX * C.MASTER_W - C.CROP_W / 2))

    # ISO1 presenter, subject crop -> 1080x1920 (carries audio)
    run(["ffmpeg", "-y", "-ss", f"{s0:.3f}", "-t", f"{dur:.3f}", "-i", C.MASTERS["ISO1"],
         "-vf", f"crop={C.CROP_W}:{C.MASTER_H}:{x0}:0,scale=1080:1920,setsar=1", *ENC, str(out / "iso1_916.mp4")])
    # ISO2 screen fit on blurred bg -> 1080x1920
    run(["ffmpeg", "-y", "-ss", f"{s0:.3f}", "-t", f"{dur:.3f}", "-i", C.MASTERS["ISO2"],
         "-filter_complex", f"[0:v]{SCREEN_FIT}[v]", "-map", "[v]", "-an",
         "-c:v", "h264_videotoolbox", "-b:v", "9000k", "-movflags", "+faststart", str(out / "iso2_916.mp4")])
    # ISO2 raw 16:9 -> 1080x608 (for split-screen / clean screen)
    run(["ffmpeg", "-y", "-ss", f"{s0:.3f}", "-t", f"{dur:.3f}", "-i", C.MASTERS["ISO2"],
         "-vf", "scale=1080:-2,setsar=1", "-an",
         "-c:v", "h264_videotoolbox", "-b:v", "9000k", "-movflags", "+faststart", str(out / "iso2_169.mp4")])

    # caption cues, reel-relative
    words = CAP.load_words(C.ANALYSIS / "transcript.json")
    cues = CAP.build_cues(words, s0, s0 + dur)
    cues = [{"start": round(cu["start"] - s0, 2), "end": round(min(cu["end"] - s0, dur), 2), "text": cu["text"]}
            for cu in cues if cu["end"] - s0 > 0]
    meta = {"id": cid, "speaker": C.SPEAKER, "color": list(C.CAPTION_COLOR),
            "duration": round(dur, 2), "hook": clip.get("hook", ""), "kind": clip.get("kind"),
            "cues": cues}
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"✓ {C.SPEAKER} clip {cid}: dur={dur:.1f}s, {len(cues)} cues -> {out}")


if __name__ == "__main__":
    main()
