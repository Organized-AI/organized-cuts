#!/usr/bin/env python3
"""04 — Build a QA contact sheet so the angle choices can be eyeballed fast.

The per-clip angle decision (talk vs. demo cutaway) is made in 02/03 from the
analysis; this step just renders reels/compare/CONTACT_SHEET.jpg — one row per
clip showing the presenter framing and, for demo clips, the screen framing.

    ./.venv/bin/python scripts/04_pick_angle.py
"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C

TILE_W, TILE_H = 360, 640
PADX, LABEL_H = 12, 96


def ascii_safe(s: str) -> str:
    """Hershey (cv2.putText) fonts only cover ASCII; map the glyphs we emit."""
    return (s or "").replace("→", "->").replace("—", "-").encode("ascii", "replace").decode()


def main():
    import cv2
    import numpy as np

    data = json.loads(C.MANIFEST_PATH.read_text())
    clips = data["clips"]
    rows = []
    for c in clips:
        tiles = []
        for key, label in (("still_person", "ISO1 person"), ("still_screen", "ISO2 screen")):
            p = c.get(key)
            img = cv2.imread(str(C.ROOT / p)) if p else None
            if img is None:
                img = np.full((TILE_H, TILE_W, 3), 40, np.uint8)
                cv2.putText(img, "—", (TILE_W // 2 - 10, TILE_H // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, (120, 120, 120), 2)
            else:
                img = cv2.resize(img, (TILE_W, TILE_H))
                star = " *" if (c["sources"] and label.split()[0] in c["sources"]) else ""
                cv2.putText(img, label + star, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            tiles.append(img)
        row = np.hstack([tiles[0], np.full((TILE_H, PADX, 3), 20, np.uint8), tiles[1]])
        label = np.full((LABEL_H, row.shape[1], 3), 20, np.uint8)
        cv2.putText(label, ascii_safe(f"[{c['id']}] {c['kind'].upper()}  {c['treatment']}"), (10, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.putText(label, ascii_safe(c["hook"])[:60], (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 210, 255), 1)
        rows.append(np.vstack([row, label]))

    sheet = np.vstack([np.pad(r, ((0, 16), (0, 0), (0, 0)), constant_values=20) for r in rows]) if rows else None
    if sheet is None:
        C.die("No clips in manifest.")
    out = C.COMPARE / "CONTACT_SHEET.jpg"
    cv2.imwrite(str(out), sheet)
    print(f"✓ Wrote {out.relative_to(C.ROOT)}  ({len(clips)} clips)")


if __name__ == "__main__":
    main()
