#!/usr/bin/env python3
"""07 — Emit viewer data for recordings.organizedai.vip.

Packages the session for the web viewer in site/: metadata, chapters (one per
reel clip), a segmented transcript, and interactive widget specs, all into one
session.json. Deterministic — no model calls; widgets come from an optional
hand-authored <project>/widgets.json (see site/README.md for the spec schema),
with timestamps snapped onto the nearest clip.

    OC_PROJECT_DIR=../session-x ./.venv/bin/python scripts/07_session_data.py

Output: <repo>/site/public/sessions/<name>/session.json (checked in, static —
the site needs no backend). Video/transcript sources are referenced by URL via
project.json "media_url" (e.g. a Drive/CDN link); absent that, the viewer
shows chapters + widgets without inline playback.
"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C

REPO_ROOT = C.CODE_ROOT.parent
SITE_SESSIONS = REPO_ROOT / "site" / "public" / "sessions"

# Group transcript words into caption-sized segments for the viewer.
SEG_MAX_WORDS = 12
SEG_MAX_GAP_S = 1.2


def load_json(p: pathlib.Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def segment_transcript(words: list[dict]) -> list[dict]:
    """[{start,end,text} words] -> [{start,end,text} phrases]."""
    segs, cur = [], []
    for w in words:
        if cur and (len(cur) >= SEG_MAX_WORDS or w["start"] - cur[-1]["end"] > SEG_MAX_GAP_S):
            segs.append(cur)
            cur = []
        cur.append(w)
    if cur:
        segs.append(cur)
    return [{"start": s[0]["start"], "end": s[-1]["end"],
             "text": " ".join(w["text"] for w in s)} for s in segs]


def snap_widget_times(widgets: list[dict], clips: list[dict]) -> list[dict]:
    """Give each widget a timestamp: keep an explicit one, else snap to its clip."""
    by_id = {c["id"]: c for c in clips}
    out = []
    for w in widgets:
        w = dict(w)
        if "t" not in w:
            clip = by_id.get(w.get("clip"))
            w["t"] = clip["start"] if clip else 0.0
        out.append(w)
    return sorted(out, key=lambda w: w["t"])


def main():
    manifest = load_json(C.MANIFEST_PATH, None) or load_json(C.CLIPS_PATH, {})
    clips = manifest.get("clips", [])
    words = load_json(C.ANALYSIS / "transcript.json", [])
    widgets = load_json(C.PROJECT_DIR / "widgets.json", [])
    name = C.CFG.get("name", C.PROJECT_DIR.name)

    session = {
        "name": name,
        "title": C.CFG.get("title", name.replace("-", " ").title()),
        "speaker": C.SPEAKER,
        "media_url": C.CFG.get("media_url"),          # optional hosted MP4/stream
        "duration": max((c["end"] for c in clips), default=0.0),
        "chapters": [
            {"id": c["id"], "title": c["hook"], "kind": c["kind"],
             "start": c["start"], "end": c["end"], "caption": c.get("caption", "")}
            for c in clips
        ],
        "transcript": segment_transcript(words),
        "widgets": snap_widget_times(widgets, clips),
    }

    out_dir = SITE_SESSIONS / name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "session.json"
    out.write_text(json.dumps(session, indent=2, ensure_ascii=False))

    # Refresh the site's session index (list page data).
    index_path = SITE_SESSIONS / "index.json"
    index = [e for e in load_json(index_path, []) if e.get("name") != name]
    index.append({"name": name, "title": session["title"], "speaker": session["speaker"],
                  "duration": session["duration"], "chapters": len(session["chapters"]),
                  "widgets": len(session["widgets"])})
    index.sort(key=lambda e: e["name"])
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))

    print(f"✓ {len(session['chapters'])} chapters, {len(session['transcript'])} transcript "
          f"segments, {len(session['widgets'])} widgets -> {out}")


if __name__ == "__main__":
    main()
