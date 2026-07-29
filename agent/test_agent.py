#!/usr/bin/env python3
"""Tests for the agent corpus stack — runnable with no network and no API key.

    python3 agent/test_agent.py

Covers: import_vault.transform (offsets, ordering, slugs), the corpus files
the repo ships with, and a live stdio JSON-RPC round-trip against server.py
(all offline tools + graceful degradation of the TwelveLabs tools).
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import import_vault  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
FAILURES = []


def check(name, cond, detail=""):
    status = "ok" if cond else "FAIL"
    print(f"  {status:<4} {name}" + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def test_transform():
    print("• import_vault.transform")
    manifest = {
        "01 - Alpha Talk.mp4": {
            "total": 5400.0,
            "parts": [
                {"label": "p1", "offset": 0, "index_id": "idxA", "video_id": "vidA"},
                {"label": "p2", "offset": 3600.0, "index_id": "idxA", "video_id": "vidB"},
            ],
        }
    }
    tx = {
        "vidA": [[10.0, 12.5, "hello world"], [100.0, 104.0, "alpha idea"]],
        "vidB": [[5.0, 9.0, "second part opens"]],
    }
    chapters = {
        "vidA": [{"start": 0, "end": 600, "title": "Intro", "summary": "s"}],
        "vidB": [{"start": 0, "end": 300, "title": "Part two"}],
    }
    comps = import_vault.transform(manifest, tx, chapters)
    check("one component per talk", len(comps) == 1)
    c = comps[0]
    check("slug", c["name"] == "vault-alpha-talk", c["name"])
    check("title strips number", c["title"] == "Alpha Talk", c["title"])
    check("duration from manifest", c["duration"] == 5400.0)
    segs = c["transcript"]
    check("transcript merged", len(segs) == 3)
    check("offset applied", any(s["start"] == 3605.0 for s in segs),
          json.dumps(segs))
    check("transcript sorted", segs == sorted(segs, key=lambda s: s["start"]))
    ch = c["clips"]
    check("chapters offset", any(x["start"] == 3600.0 for x in ch))
    check("parts kept", len(c["twelvelabs_parts"]) == 2)
    check("stream url", "recordings.organizedai.vip/media/" in c["assets"]["stream"])

    s = import_vault.site_session(c)
    check("site session chapters", len(s["chapters"]) == 2
          and s["chapters"][0]["title"] == "Intro")
    check("site session media is stream", s["media_url"] == c["assets"]["stream"])
    check("site session transcript shared", s["transcript"] is c["transcript"])


def test_corpus_files():
    print("• shipped corpus")
    idx = json.loads((REPO / "agent" / "corpus" / "corpus.json").read_text())
    check("index non-empty", len(idx) > 0)
    names = {e["name"] for e in idx}
    check("demo present", "demo" in names)
    for e in idx:
        p = REPO / "agent" / "corpus" / f"{e['name']}.json"
        if not p.exists():
            check(f"component file {e['name']}", False, "missing")
            return
    check("every index entry has a component file", True)


def test_server_stdio():
    print("• server.py over stdio JSON-RPC")
    proc = subprocess.Popen([sys.executable, str(REPO / "agent" / "server.py")],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)

    def send(m):
        proc.stdin.write(json.dumps(m) + "\n")
        proc.stdin.flush()

    def recv():
        while True:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("server died: " + proc.stderr.read()[-500:])
            if line.strip().startswith("{"):
                return json.loads(line)

    def call(name, args, rid):
        send({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
              "params": {"name": name, "arguments": args}})
        r = recv()["result"]
        return r.get("isError", False), r["content"][0]["text"]

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"}}})
        info = recv()["result"]["serverInfo"]
        check("initialize", info["name"] == "organized-cuts-corpus")
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = {t["name"] for t in recv()["result"]["tools"]}
        check("six tools", tools == {"list_sessions", "get_session",
                                     "search_transcripts", "get_clip",
                                     "find_moments", "ask_session"}, str(tools))

        err, txt = call("list_sessions", {}, 3)
        check("list_sessions", not err and len(json.loads(txt)) > 0)

        err, txt = call("get_session", {"name": "demo"}, 4)
        check("get_session", not err and len(json.loads(txt)["clips"]) == 4)

        err, txt = call("search_transcripts", {"query": "softmax temperature"}, 5)
        d = json.loads(txt)
        check("search ranked", not err and d["total"] >= 1
              and "matched" in d["matches"][0])

        err, txt = call("get_clip", {"session": "demo", "clip_id": "2"}, 6)
        check("get_clip tc", not err and json.loads(txt)["tc_in"] == "18:05")

        err, txt = call("find_moments", {"query": "x"}, 7)
        check("find_moments degrades", "TWELVELABS_API_KEY" in txt
              or "TwelveLabs ids" in txt)

        err, txt = call("get_session", {"name": "zzz"}, 8)
        check("unknown session error", err and "Unknown session" in txt)
    finally:
        proc.terminate()


def main():
    test_transform()
    test_corpus_files()
    test_server_stdio()
    if FAILURES:
        print(f"\n✗ {len(FAILURES)} failure(s): {FAILURES}")
        sys.exit(1)
    print("\n✓ all agent tests passed")


if __name__ == "__main__":
    main()
