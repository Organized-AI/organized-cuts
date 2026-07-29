#!/usr/bin/env python3
"""Package the speaker corpus into agent-ready components.

Walks every session project in the repo (any top-level dir with project.json)
plus the site's checked-in sessions, and emits one JSON component per session
under agent/corpus/ plus a corpus.json index. These are the components the
corpus MCP server (agent/server.py) serves to AI agents: exact clip timecodes,
per-clip transcripts, hooks/captions, reel files, widgets, and the TwelveLabs
index/video ids that unlock semantic moment search and grounded Q&A.

Deterministic and offline — no API calls. Sessions whose analysis data hasn't
been produced yet (or lives on another machine) still get a component with
whatever is available; re-run after each pipeline run to refresh.

    python3 agent/build_corpus.py
"""
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "agent" / "corpus"
SITE_SESSIONS = REPO / "site" / "public" / "sessions"

# Transcript segmentation (same feel as the site viewer)
SEG_MAX_WORDS = 12
SEG_MAX_GAP_S = 1.2


def load(p: pathlib.Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def segment_words(words):
    """Word list [{start,end,text}] -> phrase segments with exact timecodes."""
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


def project_component(pdir: pathlib.Path):
    cfg = load(pdir / "project.json", {})
    name = cfg.get("name", pdir.name)
    analysis = pdir / "analysis"
    state = load(analysis / "state.json", {}) or {}

    # Clips: prefer the rendered manifest (has reel paths/treatments), fall
    # back to the analysis clips (has per-clip transcripts). Merge when both.
    manifest = load(pdir / "reels" / "manifest.json", {}) or {}
    clips_analysis = (load(analysis / "clips.json", {}) or {}).get("clips", [])
    by_id = {str(c.get("id")): c for c in clips_analysis}
    clips = []
    for c in manifest.get("clips", clips_analysis):
        c = dict(c)
        extra = by_id.get(str(c.get("id")), {})
        for k in ("transcript", "score", "source", "query"):
            if k not in c and k in extra:
                c[k] = extra[k]
        clips.append(c)

    words = load(analysis / "transcript.json", []) or []
    widgets = ((load(SITE_SESSIONS / name / "session.json", {}) or {}).get("widgets")
               or load(pdir / "widgets.json", []) or [])

    return {
        "name": name,
        "title": cfg.get("title", name.replace("-", " ").title()),
        "speaker": cfg.get("speaker", "?"),
        "media_url": cfg.get("media_url"),
        "twelvelabs": {
            "index_name": cfg.get("index_name"),
            "index_id": state.get("index_id"),
            "video_id": state.get("video_id"),
        },
        "masters": cfg.get("masters", {}),
        "clips": clips,
        "transcript": segment_words(words),
        "widgets": widgets,
        "assets": {
            "reels_dir": str((pdir / "reels").relative_to(REPO)),
            "proxy": cfg.get("proxy"),
        },
    }


def site_only_component(sdir: pathlib.Path):
    """A session that exists only as site data (e.g. the demo)."""
    s = load(sdir / "session.json", {}) or {}
    return {
        "name": s.get("name", sdir.name),
        "title": s.get("title", sdir.name),
        "speaker": s.get("speaker", "?"),
        "media_url": s.get("media_url"),
        "twelvelabs": {"index_name": None, "index_id": None, "video_id": None},
        "masters": {},
        "clips": [
            {"id": c["id"], "hook": c["title"], "kind": c["kind"],
             "start": c["start"], "end": c["end"], "caption": c.get("caption", "")}
            for c in s.get("chapters", [])
        ],
        "transcript": s.get("transcript", []),
        "widgets": s.get("widgets", []),
        "assets": {},
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    components = []

    project_dirs = sorted(d for d in REPO.iterdir()
                          if d.is_dir() and (d / "project.json").exists())
    seen = set()
    for d in project_dirs:
        comp = project_component(d)
        components.append(comp)
        seen.add(comp["name"])

    if SITE_SESSIONS.exists():
        for d in sorted(SITE_SESSIONS.iterdir()):
            if d.is_dir() and d.name not in seen and (d / "session.json").exists():
                components.append(site_only_component(d))

    index = []
    for comp in components:
        (OUT_DIR / f"{comp['name']}.json").write_text(
            json.dumps(comp, indent=2, ensure_ascii=False))
        index.append({
            "name": comp["name"],
            "title": comp["title"],
            "speaker": comp["speaker"],
            "clips": len(comp["clips"]),
            "transcript_segments": len(comp["transcript"]),
            "widgets": len(comp["widgets"]),
            "twelvelabs_ready": bool(comp["twelvelabs"]["video_id"]),
        })
        print(f"  {comp['name']:<22} clips={len(comp['clips']):>3}  "
              f"segs={len(comp['transcript']):>4}  widgets={len(comp['widgets'])}  "
              f"tl={'✓' if comp['twelvelabs']['video_id'] else '–'}")

    (OUT_DIR / "corpus.json").write_text(json.dumps(index, indent=2, ensure_ascii=False))
    print(f"✓ {len(components)} session components -> {OUT_DIR.relative_to(REPO)}/")


if __name__ == "__main__":
    main()
