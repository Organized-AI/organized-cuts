#!/usr/bin/env python3
"""Restage this project's reels with their CURRENT kinds (talk/demo) into
reels/upload/, and print the Drive upload folder on stdout.

    OC_PROJECT_DIR=../session-x ./.venv/bin/python scripts/stage_upload.py
"""
import json
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C

UPDATE = "20260713"


def tc(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    return f"{h:02d}-{m:02d}-{int(s % 60):02d}"


def main():
    man = json.loads(C.MANIFEST_PATH.read_text())
    st = C.REELS / "upload"
    st.mkdir(exist_ok=True)
    for f in st.glob("*.mp4"):
        f.unlink()
    nm = C.CFG.get("name", "session")
    for c in man["clips"]:
        src = C.REELS / f"reel_{c['id']}.mp4"
        dst = st / f"{nm}_reel-{c['id']}_t{tc(c['start'])}_{UPDATE}_{c['kind']}.mp4"
        os.link(src, dst)
    print(C.UPLOAD_FOLDER)   # stdout = folder, for the shell caller


if __name__ == "__main__":
    main()
