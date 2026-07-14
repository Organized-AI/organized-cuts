#!/usr/bin/env python3
"""Compute a face-aware vertical crop position for the split-screen TOP half.

The top half shows a 960px window of the 1080x1920 presenter segment. Default
object-position (center = 50%) shows the MIDDLE band and cuts the head off.
Here we find the face's vertical centre and place it ~35% down the window.

Patches each assets/<key>/meta.json with "half_top_pos" (percent 0-100).

    ./.venv/bin/python scripts/hf_frame_fix.py <hf_assets_dir>
"""
import json
import subprocess
import sys
import pathlib
import tempfile

SRC_H, WIN_H = 1920, 960
OVERFLOW = SRC_H - WIN_H          # 960 px of vertical slack
FACE_AT = 0.35                    # put the face 35% down the visible window
TMP = pathlib.Path(tempfile.mkdtemp(prefix="framefix_", dir="/tmp"))


def face_y(video: pathlib.Path, n=5):
    """Median vertical centre (px, in the 1920-tall source) of the presenter's face."""
    import cv2
    fr = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    pr = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout.strip() or 10)
    ys = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        fp = TMP / f"f{i}.jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", str(fp)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        img = cv2.imread(str(fp))
        if img is None:
            continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = list(fr.detectMultiScale(g, 1.1, 5, minSize=(90, 90))) + \
                list(pr.detectMultiScale(g, 1.1, 5, minSize=(90, 90)))
        if faces:
            x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
            ys.append(y + h / 2)
    if not ys:
        return None
    ys.sort()
    return ys[len(ys) // 2]


def main():
    root = pathlib.Path(sys.argv[1])
    for d in sorted(root.iterdir()):
        meta = d / "meta.json"
        vid = d / "iso1_916.mp4"
        if not (meta.exists() and vid.exists()):
            continue
        m = json.loads(meta.read_text())
        fy = face_y(vid)
        if fy is None:
            pos = 0.0          # no face found -> show the very top (never cut the head)
            note = "no face; top-aligned"
        else:
            # window_top so the face lands FACE_AT down the 960px window
            top = fy - FACE_AT * WIN_H
            pos = max(0.0, min(1.0, top / OVERFLOW)) * 100
            note = f"face_y={fy:.0f}"
        m["half_top_pos"] = round(pos, 1)
        meta.write_text(json.dumps(m, indent=2))
        print(f"  {d.name:20} half_top_pos={pos:5.1f}%   ({note})")


if __name__ == "__main__":
    main()
