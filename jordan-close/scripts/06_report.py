#!/usr/bin/env python3
"""06 — Write reels/INDEX.md and print a summary table.

Source timecodes are offsets from the shared start of the frame-synced masters
(same start timecode as the proxy), formatted HH:MM:SS.mmm.

    ./.venv/bin/python scripts/06_report.py
"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C


def tc(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    return f"{h:02d}:{m:02d}:{sec % 60:06.3f}"


def main():
    data = json.loads(C.MANIFEST_PATH.read_text())
    clips = data["clips"]
    demos = sum(1 for c in clips if c["kind"] == "demo")

    lines = ["# Jordan Close — Short-Form Reels\n",
             f"Source video_id: `{data.get('video_id','?')}`  ·  {len(clips)} reels "
             f"({demos} with ISO2 screen cutaways, {len(clips)-demos} talking-head)\n",
             "One 9:16 reel per clip. Demo clips open on the presenter (ISO1) then cut "
             "to the screen feed (ISO2) with the speaker's audio kept throughout.\n",
             "QA: `reels/compare/CONTACT_SHEET.jpg`\n"]
    for c in clips:
        lines += [
            f"## Clip {c['id']} — {c['hook']}\n",
            f"- **Reel:** `{c['reel']}`",
            f"- **Kind / treatment:** {c['kind']} — {c['treatment']}  (sources: {', '.join(c['sources'])})",
            f"- **Source TC:** {tc(c['start'])} → {tc(c['end'])}  ({c['duration']:.0f}s)",
            f"- **Subject crop:** cx={c['crop_cx']} (x0={c['crop_x0']})",
            f"- **Caption:** {c['caption']}",
            "",
        ]
    C.REELS.mkdir(parents=True, exist_ok=True)
    (C.REELS / "INDEX.md").write_text("\n".join(lines))

    print(f"\n{'ID':<3} {'TC in':<12} {'Dur':>4}  {'Kind':<5} {'Treatment':<28} Hook")
    print("-" * 92)
    for c in clips:
        print(f"{c['id']:<3} {tc(c['start']):<12} {c['duration']:>3.0f}s  "
              f"{c['kind']:<5} {c['treatment'][:27]:<28} {c['hook'][:30]}")
    print(f"\n✓ Wrote {C.REELS/'INDEX.md'}")


if __name__ == "__main__":
    main()
