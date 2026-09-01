#!/usr/bin/env python3
"""Checks for master source resolution (local file vs hosted URL).

lib/common.py resolves these at import time, so each case runs in its own
interpreter. No ffmpeg needed — probe_dims() is exercised separately by the real
pipeline; this covers the path logic that decides *what* gets probed.

    python3 tests/test_sources.py
"""
import json
import pathlib
import subprocess
import sys
import tempfile

CODE_DIR = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable

PROBE = """
import json, sys
sys.path.insert(0, %r)
from lib import common as C
print(json.dumps({"sources": C.SOURCES, "iso2_present": C.ISO2_PRESENT,
                  "iso1": C.master_source("ISO1"), "iso2": C.master_source("ISO2")}))
""" % str(CODE_DIR)

URL1 = "https://videos.example.com/talk-iso1.mp4"
URL2 = "https://videos.example.com/talk-iso2.mp4"


def resolve(tmp: pathlib.Path, cfg: dict) -> dict:
    d = tmp / "proj"
    d.mkdir(exist_ok=True)
    (d / "project.json").write_text(json.dumps(cfg))
    r = subprocess.run([PY, "-c", PROBE], capture_output=True, text=True,
                       cwd=CODE_DIR, env={"OC_PROJECT_DIR": str(d), "PATH": "/usr/bin:/bin"})
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        real = tmp / "ISO1.mov"
        real.write_bytes(b"not really a movie, but it exists")
        real2 = tmp / "ISO2.mov"
        real2.write_bytes(b"also exists")

        # local masters present -> used, URLs irrelevant
        r = resolve(tmp, {"name": "p", "masters": {"ISO1": str(real), "ISO2": str(real2)},
                          "masters_url": {"ISO1": URL1, "ISO2": URL2}})
        assert r["iso1"] == str(real), r
        assert r["iso2"] == str(real2), r
        assert set(r["sources"]) == {"ISO1", "ISO2"}

        # drive detached: local paths dangle -> fall back to the hosted copies
        r = resolve(tmp, {"name": "p",
                          "masters": {"ISO1": "/Volumes/T7/gone_ISO1.MOV",
                                      "ISO2": "/Volumes/T7/gone_ISO2.MOV"},
                          "masters_url": {"ISO1": URL1, "ISO2": URL2}})
        assert r["iso1"] == URL1, r
        assert r["iso2"] == URL2, r
        assert r["iso2_present"] is True

        # attaching the drive again silently upgrades ISO1 back to local
        r = resolve(tmp, {"name": "p",
                          "masters": {"ISO1": str(real), "ISO2": "/Volumes/T7/gone.MOV"},
                          "masters_url": {"ISO1": URL1, "ISO2": URL2}})
        assert r["iso1"] == str(real) and r["iso2"] == URL2, r

        # URL given directly in `masters` is honoured as-is
        r = resolve(tmp, {"name": "p", "masters": {"ISO1": URL1}})
        assert r["iso1"] == URL1 and r["iso2"] is None, r
        assert r["iso2_present"] is False
        assert set(r["sources"]) == {"ISO1"}

        # presenter hosted, no screen feed anywhere -> demo clips degrade, not crash
        r = resolve(tmp, {"name": "p", "masters": {"ISO1": "/Volumes/T7/gone.MOV"},
                          "masters_url": {"ISO1": URL1}})
        assert r["sources"] == {"ISO1": URL1}, r
        assert r["iso2_present"] is False

        # nothing resolvable -> 03_cut_reels.py refuses via check_sources()
        r = resolve(tmp, {"name": "p", "masters": {"ISO1": "/Volumes/T7/gone.MOV"}})
        assert r["sources"] == {} and r["iso1"] is None, r

    print("✓ master source resolution checks passed")


if __name__ == "__main__":
    main()
