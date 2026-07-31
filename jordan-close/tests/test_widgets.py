#!/usr/bin/env python3
"""Offline checks for the widget + Talk Map stages (no TwelveLabs key needed).

Builds a throwaway two-part talk in a temp dir, runs 07_widgets.py --offline and
08_talkmap.py against it, and asserts the parts that are easy to break: category
colours matching the vault, part-2 timecode offsets, cross-talk linking, and the
vault-compatible {total, chapters} shape.

    python3 tests/test_widgets.py
"""
import json
import pathlib
import subprocess
import sys
import tempfile

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_DIR))
from lib import talkmap as T   # noqa: E402  (needs CODE_DIR on the path first)

PY = sys.executable
PART1_DUR = 600.0

REGISTRY = {
    "schema": "organized-cuts/talk-registry@1",
    "event": {"name": "Test Event", "city": "Austin",
              "site": "https://example.invalid",
              "vault": "https://example.invalid/vault",
              "workshops": "https://example.invalid/repo"},
    "talks": [
        {"id": "01", "speaker": "Ada", "title": "Talk One", "blurb": "b",
         "workshop": "w/one", "sessions": ["sess-a", "sess-a2"]},
        {"id": "02", "speaker": "Grace", "title": "Talk Two", "blurb": "b",
         "workshop": "w/two", "sessions": ["sess-b"]},
        {"id": "03", "speaker": "Nobody", "title": "Talk Three", "blurb": "b",
         "workshop": "w/three", "sessions": []},
    ],
}


def clip(cid, start, end, source, kind, query="", hook="", transcript=""):
    return {"id": cid, "start": start, "end": end, "duration": end - start,
            "hook": hook or f"Hook {cid}", "caption": f"Caption {cid} #ai",
            "score": 0.9, "source": source, "query": query, "kind": kind,
            "transcript": transcript or f"spoken words for clip {cid}"}


def make_session(root, name, *, base, clips, chapters, topics, reels=True):
    d = root / name
    (d / "analysis").mkdir(parents=True)
    (d / "reels").mkdir(parents=True)
    (d / "project.json").write_text(json.dumps({"name": name, "speaker": "X"}))
    (d / "analysis" / "state.json").write_text(
        json.dumps({"index_id": f"idx_{name}", "video_id": f"vid_{name}"}))
    (d / "analysis" / "clips.json").write_text(
        json.dumps({"video_id": f"vid_{name}", "clips": clips}))
    (d / "analysis" / "chapters.json").write_text(json.dumps({"chapters": chapters}))
    (d / "analysis" / "topics.json").write_text(json.dumps(topics))
    (d / "analysis" / "probes.json").write_text(json.dumps(
        {"quotable one-liner": [{"start": base + 12.0, "end": base + 30.0,
                                 "score": 0.88, "confidence": "high"}]}))
    (d / "analysis" / "transcript.json").write_text(json.dumps(
        [{"start": base + 1.0, "end": base + 1.4, "text": "Appify"},
         {"start": base + 1.4, "end": base + 1.9, "text": "actors"}]))
    if reels:
        (d / "reels" / "manifest.json").write_text(json.dumps({"clips": [
            {"id": c["id"], "kind": c["kind"], "reel": f"reels/reel_{c['id']}.mp4",
             "treatment": "ISO1 talking-head", "sources": ["ISO1"]} for c in clips]}))
    return d


def run(script, env, cwd, *args):
    r = subprocess.run([PY, str(CODE_DIR / "scripts" / script), *args],
                       capture_output=True, text=True, env=env, cwd=cwd)
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        raise AssertionError(f"{script} exited {r.returncode}")
    return r.stdout


def main():
    import os

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "talks").mkdir()
        (root / "talks" / "registry.json").write_text(json.dumps(REGISTRY))

        make_session(
            root, "sess-a", base=0.0,
            clips=[clip("01", 30, 60, "highlight", "talk"),
                   clip("02", 120, 150, "search", "demo", query="clear demo or reveal moment"),
                   clip("03", 200, 230, "search", "talk", query="quotable one-liner",
                        transcript="the Appify actor feeds the agent live data")],
            chapters=[{"start": 0, "end": 120, "title": "Introduction", "summary": "hello"},
                      {"start": 120, "end": 400, "title": "Live demo", "summary": "build"},
                      {"start": 400, "end": PART1_DUR, "title": "Q&A", "summary": "questions"}],
            topics={"title": "One", "topics": ["Apify actors", "agent memory"],
                    "hashtags": ["agents"]})
        make_session(
            root, "sess-a2", base=0.0,
            clips=[clip("01", 10, 40, "highlight", "talk")],
            chapters=[{"start": 0, "end": 300, "title": "Wrap up", "summary": "closing"}],
            topics={"title": "One B", "topics": ["agent memory"], "hashtags": []})
        make_session(
            root, "sess-b", base=0.0,
            clips=[clip("01", 15, 45, "search", "talk",
                        query="actionable takeaway builders can use")],
            chapters=[{"start": 0, "end": 500, "title": "Token costs", "summary": "pricing"}],
            topics={"title": "Two", "topics": ["agent memory", "token costs"],
                    "hashtags": ["tokens"]})

        env = dict(os.environ,
                   OC_REPO_ROOT=str(root),
                   OC_REGISTRY=str(root / "talks" / "registry.json"),
                   OC_TALKMAP_BUILD=str(root / "build"))

        for s in ("sess-a", "sess-a2", "sess-b"):
            run("07_widgets.py", dict(env, OC_PROJECT_DIR=str(root / s)),
                CODE_DIR, "--offline")

        # --- per-session widgets -------------------------------------------
        a = json.loads((root / "sess-a" / "analysis" / "widgets.json").read_text())
        assert a["schema"] == T.WIDGET_SCHEMA, a["schema"]
        assert a["talk"] == "01" and a["speaker"] == "Ada"
        assert a["duration"] == PART1_DUR, a["duration"]
        kinds = {w["type"] for w in a["widgets"]}
        for expect in ("chapter_map", "topic_index", "search_probe", "moment",
                       "demo_walkthrough", "quote", "qa_index", "reel_strip"):
            assert expect in kinds, f"missing {expect} in {sorted(kinds)}"

        cmap = next(w for w in a["widgets"] if w["type"] == "chapter_map")
        cats = [s["category"] for s in cmap["body"]["segments"]]
        assert cats == ["intro", "demo", "qa"], cats
        colors = [s["color"] for s in cmap["body"]["segments"]]
        assert colors == ["#9a927f", "#f5d623", "#b48ead"], colors   # vault TLCATS

        demo = next(w for w in a["widgets"] if w["type"] == "demo_walkthrough")
        assert demo["category"] == "demo" and demo["body"]["clip_id"] == "02"

        quote = next(w for w in a["widgets"] if w["type"] == "quote")
        assert "Apify actor" in quote["body"]["text"], quote["body"]["text"]  # Appify fixed

        b = json.loads((root / "sess-b" / "analysis" / "widgets.json").read_text())
        assert any(w["type"] == "takeaway" for w in b["widgets"])

        # --- merged bundle --------------------------------------------------
        run("08_talkmap.py", env, CODE_DIR)
        bundle = json.loads((root / "build" / "talkmap.json").read_text())
        assert bundle["schema"] == T.TALKMAP_SCHEMA
        assert bundle["counts"]["talks"] == 3
        assert bundle["counts"]["with_widgets"] == 2      # talk 03 has no sessions

        t1 = next(t for t in bundle["talks"] if t["id"] == "01")
        assert t1["total"] == PART1_DUR + 300.0, t1["total"]
        titles = [c["title"] for c in t1["chapters"]]
        assert titles == ["Introduction", "Live demo", "Q&A", "Wrap up"], titles
        wrap = next(c for c in t1["chapters"] if c["title"] == "Wrap up")
        assert wrap["start"] == PART1_DUR and wrap["end"] == PART1_DUR + 300.0, wrap
        p2 = [w for w in t1["widgets"] if w["session"] == "sess-a2"]
        assert p2 and all(w["start"] >= PART1_DUR for w in p2), \
            [(w["id"], w["start"]) for w in p2]
        # seek actions must be shifted too, or the player jumps to the wrong place
        for w in p2:
            for act in w["actions"]:
                if act.get("kind") == "seek":
                    assert act["t"] >= PART1_DUR, (w["id"], act)

        # "agent memory" is in talks 01 and 02 -> reciprocal cross_talk links
        cross = [w for w in t1["widgets"] if w["type"] == "cross_talk"]
        assert cross, "expected a cross-talk link for the shared topic"
        assert any(o["talk"] == "02" for w in cross for o in w["body"]["also_in"])
        t3 = next(t for t in bundle["talks"] if t["id"] == "03")
        assert t3["widgets"] == [] and t3["total"] == 0.0

        # --- vault-compatible per-talk payload -------------------------------
        api = json.loads((root / "build" / "talks" / "01.json").read_text())
        assert set(("total", "chapters", "widgets")) <= set(api)
        for ch in api["chapters"]:
            assert {"start", "end", "title", "summary"} <= set(ch)
            assert ch["end"] >= ch["start"]
        prev = (root / "build" / "index.html").read_text()
        assert "TALK MAP" in prev and "Talk One" in prev

        # --- registry guards --------------------------------------------------
        bad = json.loads(json.dumps(REGISTRY))
        bad["talks"][1]["sessions"].append("sess-a")
        (root / "talks" / "bad.json").write_text(json.dumps(bad))
        try:
            T.load_registry(root / "talks" / "bad.json")
        except ValueError as e:
            assert "exactly one talk" in str(e)
        else:
            raise AssertionError("duplicate session should have been rejected")

    print("✓ all widget + talk map checks passed")


if __name__ == "__main__":
    main()
