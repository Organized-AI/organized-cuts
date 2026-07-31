#!/usr/bin/env python3
"""Checks for import_talkmap.py against a synthetic vault export.

Covers the two cases that matter: counts agreeing (pair in order, write the
vault's chapters through) and counts disagreeing (refuse, explain, exit 2) —
which is exactly what a talk with four session dirs and two recordings does.

    python3 tests/test_import.py
"""
import json
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
        {"id": "01", "speaker": "Ada", "title": "One", "blurb": "", "workshop": "",
         "sessions": ["sess-a", "sess-a2"]},
        {"id": "02", "speaker": "Grace", "title": "Two", "blurb": "", "workshop": "",
         "sessions": ["sess-b", "sess-b2", "sess-b3"]},   # 3 dirs, 1 recording
    ],
}

EXPORT = {
    "videos": [
        {"key": "01 Ada — One part 1.mp4", "title": "Ada — One (1/2)", "size": 1},
        {"key": "01 Ada — One part 2.mp4", "title": "Ada — One (2/2)", "size": 1},
        {"key": "02 Grace — Two.mp4", "title": "Grace — Two", "size": 1},
        {"key": "99 Stray.mp4", "title": "Not in registry", "size": 1},
        {"key": "no-prefix.mp4", "title": "Orphan", "size": 1},
    ],
    "chapters": {
        "01 Ada — One part 1.mp4": {"total": 600, "chapters": [
            {"start": 0, "end": 300, "title": "Introduction", "summary": "hi"},
            {"start": 300, "end": 600, "title": "Live demo", "summary": "build"}]},
        "01 Ada — One part 2.mp4": {"total": 300, "chapters": [
            {"start": 0, "end": 300, "title": "Q&A", "summary": "questions"}]},
        "02 Grace — Two.mp4": {"total": 500, "chapters": [
            {"start": 0, "end": 500, "title": "Token costs", "summary": "pricing"}]},
    },
}


def run(root, export, *args):
    import os
    env = dict(os.environ, OC_REPO_ROOT=str(root),
               OC_REGISTRY=str(root / "talks" / "registry.json"))
    return subprocess.run(
        [PY, str(CODE_DIR / "scripts" / "import_talkmap.py"), str(export), *args],
        capture_output=True, text=True, env=env, cwd=CODE_DIR)


def main():
    with tempfile.TemporaryDirectory() as t:
        root = pathlib.Path(t)
        (root / "talks").mkdir()
        (root / "talks" / "registry.json").write_text(json.dumps(REGISTRY))
        for s in ("sess-a", "sess-a2", "sess-b", "sess-b2", "sess-b3"):
            (root / s / "analysis").mkdir(parents=True)
        exp = root / "export.json"
        exp.write_text(json.dumps(EXPORT))

        # dry run: reports, writes nothing, exits 2 because talk 02 is ambiguous
        r = run(root, exp)
        assert r.returncode == 2, r.stdout + r.stderr
        assert not (root / "sess-a" / "analysis" / "chapters.json").exists()
        assert "would write" in r.stdout, r.stdout
        assert "no NN talk prefix" in r.stdout, r.stdout
        assert "absent from the registry" in r.stdout, r.stdout   # the 99 key
        assert "3 registry session(s)" in r.stdout, r.stdout       # talk 02 mismatch

        # --write applies the unambiguous pairs (talk 01) and still flags talk 02
        r = run(root, exp, "--write")
        assert r.returncode == 2, r.stdout
        a = json.loads((root / "sess-a" / "analysis" / "chapters.json").read_text())
        assert a["total"] == 600 and len(a["chapters"]) == 2, a
        assert a["chapters"][0]["title"] == "Introduction"
        assert a["imported_from"]["vault_key"] == "01 Ada — One part 1.mp4"
        a2 = json.loads((root / "sess-a2" / "analysis" / "chapters.json").read_text())
        assert a2["chapters"][0]["title"] == "Q&A", a2
        assert not (root / "sess-b" / "analysis" / "chapters.json").exists()

        # explicit --map resolves the ambiguous talk
        r = run(root, exp, "--write", "--map", "02 Grace — Two.mp4=sess-b2")
        b2 = json.loads((root / "sess-b2" / "analysis" / "chapters.json").read_text())
        assert b2["chapters"][0]["title"] == "Token costs", b2

        # imported chapters are what 07_widgets.py consumes
        doc = json.loads((root / "sess-a" / "analysis" / "chapters.json").read_text())
        assert {"total", "chapters"} <= set(doc)

    print("✓ vault import checks passed")


if __name__ == "__main__":
    main()
