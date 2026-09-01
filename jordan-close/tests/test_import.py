#!/usr/bin/env python3
"""Checks for import_talkmap.py and the vault map taking precedence in 08.

The vault serves one consolidated recording per talk, so its chapters describe
the whole talk — not any single session dir. These cover that: the import lands
at talk level, and 08 then uses it instead of stitching per-part spines.

    python3 tests/test_import.py
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable

REGISTRY = {
    "schema": "organized-cuts/talk-registry@1",
    "event": {"name": "T", "city": "C", "site": "s", "vault": "v", "workshops": "w"},
    "talks": [
        # one vault recording, four session dirs — the real Michael shape
        {"id": "01", "speaker": "Ada", "title": "One", "blurb": "", "workshop": "",
         "sessions": ["sess-a", "sess-a2"]},
        {"id": "02", "speaker": "Grace", "title": "Two", "blurb": "", "workshop": "",
         "sessions": []},
    ],
}

EXPORT = {
    "videos": [
        {"key": "01 — Ada — One.mp4", "title": "Ada — One", "size": 1},
        {"key": "02 — Grace — Two.mp4", "title": "Grace — Two", "size": 1},
        {"key": "99 — Stray.mp4", "title": "Not in registry", "size": 1},
        {"key": "no-prefix.mp4", "title": "Orphan", "size": 1},
    ],
    "chapters": {
        "01 — Ada — One.mp4": {"total": 2400, "chapters": [
            {"start": 0, "end": 180, "title": "Introduction", "summary": "hello"},
            {"start": 180, "end": 1500, "title": "Live demo", "summary": "builds it"},
            {"start": 1500, "end": 2100, "title": "Token costs", "summary": "pricing"},
            {"start": 2100, "end": 2400, "title": "Q&A", "summary": "questions"}]},
        "02 — Grace — Two.mp4": {"total": 500, "chapters": [
            {"start": 0, "end": 500, "title": "Appify actors", "summary": "tools"}]},
    },
}


def run(script, root, *args):
    env = dict(os.environ, OC_REPO_ROOT=str(root),
               OC_REGISTRY=str(root / "talks" / "registry.json"),
               OC_TALKMAP_BUILD=str(root / "build"))
    return subprocess.run([PY, str(CODE_DIR / "scripts" / script), *args],
                          capture_output=True, text=True, env=env, cwd=CODE_DIR)


def main():
    with tempfile.TemporaryDirectory() as t:
        root = pathlib.Path(t)
        (root / "talks").mkdir()
        (root / "talks" / "registry.json").write_text(json.dumps(REGISTRY))
        for s in ("sess-a", "sess-a2"):
            (root / s / "analysis").mkdir(parents=True)
            (root / s / "project.json").write_text(json.dumps({"name": s}))
        exp = root / "export.json"
        exp.write_text(json.dumps(EXPORT))

        # dry run reports but writes nothing
        r = run("import_talkmap.py", root, str(exp))
        assert r.returncode == 0, r.stdout + r.stderr
        assert not (root / "talks" / "chapters").exists()
        assert "would write" in r.stdout, r.stdout
        assert "no NN talk prefix" in r.stdout, r.stdout
        assert "not in the registry" in r.stdout, r.stdout        # the 99 key
        assert "Live Demo 1" in r.stdout, r.stdout                # category summary

        # --write lands the map at talk level, not per session
        r = run("import_talkmap.py", root, str(exp), "--write")
        assert r.returncode == 0, r.stdout + r.stderr
        c1 = json.loads((root / "talks" / "chapters" / "01.json").read_text())
        assert c1["total"] == 2400 and len(c1["chapters"]) == 4, c1
        assert c1["imported_from"]["vault_key"] == "01 — Ada — One.mp4"
        assert not (root / "sess-a" / "analysis" / "chapters.json").exists()

        # 08 uses the vault map: one talk-level spine covering the whole talk
        r = run("08_talkmap.py", root)
        assert r.returncode == 0, r.stdout + r.stderr
        bundle = json.loads((root / "build" / "talkmap.json").read_text())
        t1 = next(x for x in bundle["talks"] if x["id"] == "01")
        assert t1["total"] == 2400.0, t1["total"]
        assert [c["title"] for c in t1["chapters"]] == [
            "Introduction", "Live demo", "Token costs", "Q&A"]
        maps = [w for w in t1["widgets"] if w["type"] == "chapter_map"]
        assert len(maps) == 1, [w["id"] for w in maps]     # not one per session part
        assert maps[0]["source"] == "vault:/api/chapters"
        assert maps[0]["session"] == ""                     # talk-level, not a part
        cats = [s["category"] for s in maps[0]["body"]["segments"]]
        assert cats == ["intro", "demo", "data", "qa"], cats
        qa = [w for w in t1["widgets"] if w["type"] == "qa_index"]
        assert len(qa) == 1 and qa[0]["body"]["count"] == 1, qa

        # a talk with no session dirs still gets its map from the vault
        t2 = next(x for x in bundle["talks"] if x["id"] == "02")
        assert t2["total"] == 500.0 and len(t2["chapters"]) == 1, t2
        m2 = next(w for w in t2["widgets"] if w["type"] == "chapter_map")
        # ASR fix travels with the imported text
        assert m2["body"]["segments"][0]["title"] == "Apify actors", m2

        api = json.loads((root / "build" / "talks" / "01.json").read_text())
        assert api["total"] == 2400 and len(api["chapters"]) == 4

    print("✓ vault import + talk-level map checks passed")


if __name__ == "__main__":
    main()
