#!/usr/bin/env python3
"""Score the ISO2 screen content at each TALK clip's midpoint, so we can promote
the best ones to 'demo' (screenshare + speaker). Blank/idle screens score low.

    OC_PROJECT_DIR=../session-x ./.venv/bin/python scripts/demo_candidates.py [--promote N]
"""
import json
import subprocess
import sys
import pathlib
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C

TMP = pathlib.Path(tempfile.mkdtemp(prefix="demoscore_", dir="/tmp"))


def score_screen(t):
    """Content score of the ISO2 frame at time t: 0 = blank, higher = busy screen."""
    import cv2
    fp = TMP / f"s_{int(t)}.jpg"
    subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", C.MASTERS["ISO2"],
                    "-frames:v", "1", "-vf", "scale=640:-1", str(fp)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    img = cv2.imread(str(fp))
    if img is None:
        return 0.0, 0.0, 0.0
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    std = float(g.std())                                   # tonal spread
    edges = cv2.Canny(g, 80, 160)
    edge = float((edges > 0).mean()) * 100                  # % edge pixels ~ text/UI density
    return round(std + edge * 4, 1), round(std, 1), round(edge, 2)


def main():
    promote = 0
    if "--promote" in sys.argv:
        promote = int(sys.argv[sys.argv.index("--promote") + 1])
    if not C.ISO2_PRESENT:
        C.die(f"{C.CFG.get('name')} has no ISO2 — demo reels impossible.")
    data = json.loads(C.CLIPS_PATH.read_text())
    talk = [c for c in data["clips"] if c["kind"] == "talk"]
    demo_now = sum(1 for c in data["clips"] if c["kind"] == "demo")

    scored = []
    for c in talk:
        mid = (c["start"] + c["end"]) / 2
        s, std, edge = score_screen(mid)
        scored.append((s, std, edge, c))
    scored.sort(key=lambda x: -x[0])

    print(f"{C.CFG.get('name','?')}: {demo_now} demo now, {len(talk)} talk")
    for s, std, edge, c in scored:
        print(f"  [{c['id']}] score={s:6.1f} (std={std:5.1f} edge={edge:4.2f}%)  {c['hook'][:40]}")

    if promote:
        ids = [c["id"] for s, _, _, c in scored[:promote]]
        for c in data["clips"]:
            if c["id"] in ids:
                c["kind"] = "demo"
        C.CLIPS_PATH.write_text(json.dumps(data, indent=2))
        print(f"\n✓ promoted to demo: {ids}  (now {demo_now + len(ids)} demo)")
        print("PROMOTED " + ",".join(ids))


if __name__ == "__main__":
    main()
