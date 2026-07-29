#!/usr/bin/env python3
"""Organized Cuts corpus MCP server — hand the speaker corpus to any AI agent.

Serves the components built by agent/build_corpus.py so an agent can answer
questions about the entire corpus with exact details and precise clips:

Offline (corpus JSON only):
  list_sessions        corpus overview
  get_session          one session: clips, transcript, widgets, TwelveLabs ids
  search_transcripts   lexical search, exact timecodes, across all sessions
  get_clip             a clip's exact source timecodes, copy, and reel file

With TWELVELABS_API_KEY (uses each session's existing index):
  find_moments         Marengo semantic search -> ranked moments w/ timecodes
  ask_session          Pegasus grounded Q&A over the session video

Run over stdio (what agents mount):
    python3 agent/server.py
"""
import json
import os
import pathlib
import re
import sys

try:                                    # mcp >= 2.0
    from mcp.server import MCPServer as _Server
except ImportError:                     # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

REPO = pathlib.Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO / "agent" / "corpus"

server = _Server(
    name="organized-cuts-corpus",
    instructions=(
        "Speaker-session corpus for Organized AI workshops. Start with "
        "list_sessions; use search_transcripts for exact quotes and timecodes; "
        "find_moments/ask_session add TwelveLabs semantic search and grounded "
        "answers when an API key is configured. Timecodes are seconds from the "
        "start of the session's frame-synced masters."
    ),
)


# --- corpus access ----------------------------------------------------------

def _index() -> list[dict]:
    p = CORPUS_DIR / "corpus.json"
    if not p.exists():
        raise RuntimeError("Corpus not built — run: python3 agent/build_corpus.py")
    return json.loads(p.read_text())


def _session(name: str) -> dict:
    p = CORPUS_DIR / f"{name}.json"
    if not p.exists():
        known = ", ".join(e["name"] for e in _index())
        raise ValueError(f"Unknown session '{name}'. Known: {known}")
    return json.loads(p.read_text())


def _fmt_tc(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# --- offline tools ----------------------------------------------------------

@server.tool()
def list_sessions() -> str:
    """Corpus overview: every session with speaker, clip/transcript/widget
    counts, and whether TwelveLabs semantic tools are available for it."""
    return json.dumps(_index(), indent=2, ensure_ascii=False)


@server.tool()
def get_session(name: str) -> str:
    """Full detail for one session: clips (exact start/end seconds, hooks,
    captions, per-clip transcripts, reel files), the segmented transcript,
    interactive widget specs, and TwelveLabs index/video ids."""
    return json.dumps(_session(name), indent=2, ensure_ascii=False)


@server.tool()
def search_transcripts(query: str, session: str | None = None, limit: int = 12) -> str:
    """Find where something was said, with exact timecodes. Case-insensitive
    lexical search over every session transcript (or one session): segments
    are ranked by how many query words they contain, full matches first. Works
    offline. For fuzzy/semantic matching use find_moments instead."""
    words = [w for w in re.findall(r"\w+", query.lower()) if w]
    if not words:
        raise ValueError("Empty query.")
    names = [session] if session else [e["name"] for e in _index()]
    hits = []
    for n in names:
        comp = _session(n)
        for seg in comp["transcript"]:
            low = seg["text"].lower()
            matched = [w for w in words if w in low]
            if matched:
                hits.append({"session": n, "speaker": comp["speaker"],
                             "start": seg["start"], "end": seg["end"],
                             "tc": _fmt_tc(seg["start"]), "text": seg["text"],
                             "matched": matched})
    hits.sort(key=lambda h: (-len(h["matched"]), h["session"], h["start"]))
    return json.dumps({"query": query, "matches": hits[:limit],
                       "total": len(hits)}, indent=2, ensure_ascii=False)


@server.tool()
def get_clip(session: str, clip_id: str) -> str:
    """One clip's exact source timecodes, duration, hook/caption copy,
    per-clip transcript, and rendered reel file path."""
    comp = _session(session)
    for c in comp["clips"]:
        if str(c.get("id")) == str(clip_id):
            out = dict(c)
            out["tc_in"], out["tc_out"] = _fmt_tc(c["start"]), _fmt_tc(c["end"])
            out["session"], out["speaker"] = session, comp["speaker"]
            return json.dumps(out, indent=2, ensure_ascii=False)
    ids = [str(c.get("id")) for c in comp["clips"]]
    raise ValueError(f"No clip '{clip_id}' in {session}. Clips: {ids}")


# --- TwelveLabs-backed tools ------------------------------------------------

def _tl_client():
    key = os.environ.get("TWELVELABS_API_KEY", "").strip()
    if not key:
        for envf in (REPO / "jordan-close" / ".env",):
            if envf.exists():
                m = re.search(r"^TWELVELABS_API_KEY=(.+)$", envf.read_text(), re.M)
                if m:
                    key = m.group(1).strip().strip('"').strip("'")
                    break
    if not key:
        raise RuntimeError(
            "TWELVELABS_API_KEY not set — semantic tools unavailable. "
            "Offline alternatives: search_transcripts, get_session."
        )
    from twelvelabs import TwelveLabs
    return TwelveLabs(api_key=key)


def _dump(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_dump(x) for x in obj]
    return obj


def _tl_sessions(session: str | None):
    names = [session] if session else [e["name"] for e in _index()]
    ready = []
    for n in names:
        comp = _session(n)
        tl = comp.get("twelvelabs") or {}
        if tl.get("index_id") and tl.get("video_id"):
            ready.append((n, comp, tl))
    if not ready:
        raise RuntimeError(
            "No session with TwelveLabs ids in the corpus"
            + (f" (asked for '{session}')" if session else "")
            + ". Run the pipeline's 01_ingest first, then rebuild the corpus."
        )
    return ready


@server.tool()
def find_moments(query: str, session: str | None = None, limit: int = 8) -> str:
    """Semantic moment search via TwelveLabs Marengo over the session's
    existing index: natural-language queries like 'the QR-code demo' return
    ranked moments with exact start/end seconds. Searches every indexed
    session unless `session` narrows it. Requires TWELVELABS_API_KEY."""
    client = _tl_client()
    results = []
    for n, comp, tl in _tl_sessions(session):
        try:
            pager = client.search.query(
                index_id=tl["index_id"],
                search_options=["visual", "audio"],
                query_text=query,
                group_by="clip",
                page_limit=limit,
            )
        except Exception as e:
            results.append({"session": n, "error": str(e)})
            continue
        for item in pager:
            d = _dump(item)
            st, en = d.get("start"), d.get("end")
            if st is None or en is None:
                continue
            score = d.get("score")
            if score is None:
                score = {"high": 0.9, "medium": 0.7, "low": 0.5}.get(
                    d.get("confidence"), 0.75)
            results.append({"session": n, "speaker": comp["speaker"],
                            "start": float(st), "end": float(en),
                            "tc": _fmt_tc(float(st)), "score": float(score)})
            if sum(1 for r in results if r.get("session") == n and "start" in r) >= limit:
                break
    results.sort(key=lambda r: r.get("score", 0), reverse=True)
    return json.dumps({"query": query, "moments": results[:limit]},
                      indent=2, ensure_ascii=False)


@server.tool()
def ask_session(question: str, session: str, max_tokens: int = 1200) -> str:
    """Grounded Q&A over one session's video via TwelveLabs Pegasus — answers
    come from the indexed video itself (visuals + audio), not just text. Ask
    for timestamps in the question to get timecoded citations. Requires
    TWELVELABS_API_KEY."""
    client = _tl_client()
    ready = _tl_sessions(session)
    n, comp, tl = ready[0]
    prompt = (
        f"Answer using only this video of {comp['speaker']}'s session. "
        "Cite exact timestamps in seconds for every claim. "
        f"Question: {question}"
    )
    res = _dump(client.analyze(model_name="pegasus1.2", video_id=tl["video_id"],
                               prompt=prompt, temperature=0.2,
                               max_tokens=max_tokens))
    return json.dumps({"session": n, "question": question,
                       "answer": res.get("data") or ""},
                      indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # stdio transport — stdout is the protocol channel, so keep prints off it.
    print(f"organized-cuts-corpus: serving {CORPUS_DIR}", file=sys.stderr)
    server.run("stdio")
