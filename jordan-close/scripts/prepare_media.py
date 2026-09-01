#!/usr/bin/env python3
"""Generate the 720p proxy (for TwelveLabs) and the mono 16k audio (for Whisper)
from this project's ISO1 master. Idempotent.

    OC_PROJECT_DIR=../session-3-rohit ./.venv/bin/python scripts/prepare_media.py
"""
import subprocess
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C


def main():
    iso1 = C.master_source("ISO1")
    if not iso1:
        C.die("ISO1 master not found.\n"
              f"  Local: {C.MASTERS.get('ISO1') or '(unset)'}\n"
              f"  URL:   {C.MASTERS_URL.get('ISO1') or '(unset)'}\n"
              "  Attach the drive, or add `masters_url` to project.json.")
    label = iso1 if C.is_url(iso1) else pathlib.Path(iso1).name
    C.PROXY.parent.mkdir(parents=True, exist_ok=True)
    C.ANALYSIS.mkdir(parents=True, exist_ok=True)

    if C.PROXY.exists():
        print(f"• proxy exists: {C.PROXY}")
    else:
        print(f"• generating 720p proxy from {label}…")
        subprocess.run(["ffmpeg", "-y", "-i", iso1, "-vf", "scale=-2:720",
                        "-c:v", "h264_videotoolbox", "-b:v", "2500k",
                        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                        str(C.PROXY)], check=True)

    wav = C.ANALYSIS / "iso1_audio.wav"
    if wav.exists():
        print(f"• audio exists: {wav}")
    else:
        print("• extracting 16k mono audio for Whisper…")
        subprocess.run(["ffmpeg", "-y", "-i", iso1, "-ac", "1", "-ar", "16000", str(wav)], check=True)
    print(f"✓ proxy={C.PROXY.name} ({C.PROXY.stat().st_size/1e6:.0f} MB)  audio={wav.name}")


if __name__ == "__main__":
    main()
