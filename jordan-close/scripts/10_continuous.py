#!/usr/bin/env python3
"""10 — Build a previewable copy of the continuous long-cut page.

talkmap/vault/continuous.html ships with no chapter data: on the vault it
fetches /api/videos and /api/chapters itself. This injects the merged bundle
into that same page so the subject index can be explored without a member
session — the map is live, the video is not.

    ./.venv/bin/python scripts/10_continuous.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import talkmap as T

TEMPLATE = T.REPO_ROOT / "talkmap" / "vault" / "continuous.html"
OUT = T.BUILD_DIR / "continuous-preview.html"


def main():
    bundle_path = T.BUILD_DIR / "talkmap.json"
    bundle = T.read_json(bundle_path)
    if not bundle:
        sys.exit(f"No bundle at {bundle_path}. Run 08_talkmap.py first.")

    talks = []
    for t in bundle["talks"]:
        if not t["chapters"]:
            continue
        meta = T.load_talk_chapters(t["id"]) or {}
        key = (meta.get("imported_from") or {}).get("vault_key") or f"{t['id']} {t['speaker']}.mp4"
        talks.append({
            "id": t["id"], "key": key, "speaker": t["speaker"],
            "title": f"{t['speaker']} — {t['title']}",
            "total": t["total"],
            "chapters": [{"start": c["start"], "end": c["end"], "title": c["title"],
                          "summary": c["summary"], "category": c["category"],
                          "color": c["color"]} for c in t["chapters"]],
        })
    if not talks:
        sys.exit("No talks carry chapters yet — run import_talkmap.py --write.")

    html = TEMPLATE.read_text().replace(
        "/*__DATA__*/null", json.dumps({"talks": talks}, separators=(",", ":")), 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)

    total = sum(t["total"] for t in talks)
    print(f"• {len(talks)} talks, {sum(len(t['chapters']) for t in talks)} chapters, "
          f"{total/3600:.2f}h continuous")
    print(f"✓ {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
