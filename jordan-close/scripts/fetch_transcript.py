#!/usr/bin/env python3
"""Cache the full timed transcript -> analysis/transcript.json (list of
{start,end,text}). Used to build burned-in captions in 03.

    ./.venv/bin/python scripts/fetch_transcript.py
"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C

OUT = C.ANALYSIS / "transcript.json"


def main():
    st = C.require_state("index_id", "video_id")
    client = C.client()
    v = C.dump(client.indexes.videos.retrieve(st["index_id"], st["video_id"], transcription=True))
    segs = []
    for s in (v.get("transcription") or []):
        s = C.dump(s)
        if s.get("start") is not None and s.get("end") is not None:
            segs.append({"start": float(s["start"]), "end": float(s["end"]),
                         "text": (s.get("value") or s.get("text") or "").strip()})
    segs.sort(key=lambda x: x["start"])
    OUT.write_text(json.dumps(segs, indent=2))
    lens = [len(s["text"].split()) for s in segs if s["text"]]
    print(f"✓ {len(segs)} segments -> {OUT}")
    if lens:
        print(f"  avg words/segment: {sum(lens)/len(lens):.1f} | sample: {segs[len(segs)//2]}")


if __name__ == "__main__":
    main()
