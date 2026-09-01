"""Talk Map + widget model — shared by 07_widgets.py and 08_talkmap.py.

The vault at recordings.organizedai.vip/vault already renders a Talk Map (SPINE /
ORBIT) from Pegasus chapters, colouring each segment by a category derived from
the chapter title. This module is the pipeline-side half of that contract: the
same six categories, the same colours, the same transcription fixes — so widgets
generated here drop straight onto the existing map without re-tinting anything.

Deliberately dependency-free (stdlib only) and independent of lib/common.py, so
08_talkmap.py can walk every session without binding to one OC_PROJECT_DIR.
"""
from __future__ import annotations

import json
import os
import pathlib
import re

CODE_ROOT = pathlib.Path(__file__).resolve().parent.parent      # jordan-close/
# Sessions live beside the code dir. OC_REPO_ROOT relocates that whole tree,
# which is what the fixture tests use to run against a throwaway repo.
REPO_ROOT = pathlib.Path(os.environ.get("OC_REPO_ROOT", str(CODE_ROOT.parent))).resolve()
REGISTRY_PATH = pathlib.Path(
    os.environ.get("OC_REGISTRY", str(REPO_ROOT / "talks" / "registry.json"))
)
BUILD_DIR = pathlib.Path(
    os.environ.get("OC_TALKMAP_BUILD", str(REPO_ROOT / "talkmap" / "build"))
)
# The vault serves one consolidated recording per talk, so its chapters describe
# the whole talk rather than any single session dir. They land here, keyed by
# talk id, and 08 prefers them over anything stitched from session parts.
TALK_CHAPTERS_DIR = REPO_ROOT / "talks" / "chapters"

WIDGET_SCHEMA = "organized-cuts/talk-widgets@1"
TALKMAP_SCHEMA = "organized-cuts/talk-map@1"

# --- Categories -------------------------------------------------------------
# The vault renders these; keep ids/colours/patterns in sync with its TLCATS or
# the map re-colours itself (docs/TALK-MAP-WIDGETS.md carries the JS to paste).
CATEGORIES = [
    {"id": "intro", "label": "Intro / Wrap", "color": "#9a927f",
     "pattern": r"\bintro\b|\bintroduc(?:tion|ing)\b|welcome|journey|opening|closing|wrap[- ]?up|outro|recap|appreciation|thank"},
    {"id": "qa", "label": "Q&A", "color": "#b48ead",
     "pattern": r"q\s*&\s*a|\bquestions?\b|audience|discussion"},
    {"id": "data", "label": "Data / Tokens", "color": "#e0985a",
     "pattern": r"\btokens?\b|\bcosts?\b|pricing|benchmark|\bresults?\b|\bmetrics?\b|\bstat(?:s|istics)?\b|performance"},
    {"id": "demo", "label": "Live Demo", "color": "#f5d623",
     "pattern": r"\bdemos?\b|\bdemonstrat\w*|\blive\b|walk-?through|hands-on|\bcoding\b|\bscreen\b"},
    {"id": "build", "label": "Build / Workflow", "color": "#59a5a0",
     "pattern": r"\bworkflows?\b|\bworkers?\b|\bskills?\b|\bbuild(?:ing)?\b|automat\w*|\barchitectures?\b|\bpipelines?\b|orchestrat\w*"},
    {"id": "tools", "label": "Tools / Platform", "color": "#90b97e",
     "pattern": r"\bplatforms?\b|\bmcp\b|\bsetup\b|install\w*|integrat\w*|\bapis?\b|\bsdk\b|\bstack\b|\btool(?:s|box|ing)?\b|config\w*|deploy\w*"},
    {"id": "concept", "label": "Concepts", "color": "#7aa2c9", "pattern": r"."},
]
_CAT_RX = [(c, re.compile(c["pattern"], re.I)) for c in CATEGORIES]
CATEGORY_BY_ID = {c["id"]: c for c in CATEGORIES}
FALLBACK_CATEGORY = CATEGORIES[-1]

# Scoring, not first-match. Under first-match an earlier category's passing
# mention in a summary beat a later category's explicit title — "Workflow
# Overview" landed in Q&A because its summary said "questions". A title is a
# deliberate label and now outweighs any summary; among summaries, more distinct
# hits win. The threshold is 1 because a lone summary word is still better
# evidence than nothing: raising it to 2 pushed 70% of Rohit's, Shep's and
# Henry's chapters into Concepts, trading one dominant colour for another.
TITLE_SCORE = 3
SUMMARY_SCORE = 1
MAX_SUMMARY_SCORE = 2
MIN_SCORE = 1


def categorize(title: str, summary: str = "") -> dict:
    """Highest-scoring category, ties going to the earlier one in CATEGORIES."""
    best, best_score = None, 0
    for cat, rx in _CAT_RX[:-1]:
        if rx.search(title or ""):
            score = TITLE_SCORE
        else:
            distinct = {m.group(0).lower() for m in rx.finditer(summary or "")}
            score = min(len(distinct) * SUMMARY_SCORE, MAX_SUMMARY_SCORE)
        if score > best_score:
            best, best_score = cat, score
    return best if best_score >= MIN_SCORE else FALLBACK_CATEGORY


# --- Transcription fixes ----------------------------------------------------
# Names ASR reliably mangles across these talks. The vault patches chapter text
# client-side; we patch every string a widget carries, so the fix travels with
# the data instead of being re-applied per surface.
TEXT_FIXES = [
    (re.compile(r"\bAppify\b", re.I), "Apify"),
    (re.compile(r"\bCloud Code\b", re.I), "Claude Code"),
    (re.compile(r"\bQuinn\b"), "Qwen"),
    (re.compile(r"\bQIN\b"), "Qwen"),            # Esteban, "QIN models" on the benchmark
    (re.compile(r"\bLight Alarm\b", re.I), "LiteLLM"),
    (re.compile(r"\bLightLM\b"), "LiteLLM"),     # Henry, listing routers alongside Haiku
    (re.compile(r"\bLang ?fuse\b", re.I), "Langfuse"),
]


def fix_text(s: str) -> str:
    s = s or ""
    for rx, repl in TEXT_FIXES:
        s = rx.sub(repl, s)
    return s


# --- Timecodes --------------------------------------------------------------
def fmt_t(sec: float) -> str:
    """M:SS — matches the vault's fmtT for chip/hub labels."""
    sec = max(0.0, float(sec))
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def fmt_tc(sec: float) -> str:
    """HH:MM:SS.mmm — matches 06_report.py source timecodes."""
    sec = max(0.0, float(sec))
    return f"{int(sec // 3600):02d}:{int((sec % 3600) // 60):02d}:{sec % 60:06.3f}"


# --- Registry ---------------------------------------------------------------
def load_registry(path: pathlib.Path | None = None) -> dict:
    p = path or REGISTRY_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"Talk registry not found at {p}. It maps session dirs to the talks on "
            "recordings.organizedai.vip; create it or set OC_REGISTRY."
        )
    reg = json.loads(p.read_text())
    seen = {}
    for t in reg.get("talks", []):
        for s in t.get("sessions", []):
            if s in seen:
                raise ValueError(
                    f"Session {s!r} is claimed by talks {seen[s]!r} and {t['id']!r} "
                    f"in {p}. A session belongs to exactly one talk."
                )
            seen[s] = t["id"]
    return reg


def talk_for_session(session: str, reg: dict | None = None) -> dict | None:
    """The talk a session dir belongs to, or None if it is unmapped."""
    reg = reg or load_registry()
    for t in reg.get("talks", []):
        if session in t.get("sessions", []):
            return t
    return None


def session_dir(name: str) -> pathlib.Path:
    return REPO_ROOT / name


# --- Widgets ----------------------------------------------------------------
# A widget is one interactive thing the vault can render beside the player. Every
# widget is anchored to a time range on the talk and carries the TwelveLabs
# signal it came from, so the site can show provenance and the pipeline can be
# re-run without guessing what was model-generated.
WIDGET_TYPES = (
    "chapter_map",        # Pegasus chapters — the map spine itself
    "moment",             # a Pegasus highlight, optionally linked to a cut reel
    "demo_walkthrough",   # clip classified as a screen demo (ISO2 feed)
    "quote",              # quotable one-liner (Marengo search + transcript)
    "takeaway",           # actionable takeaway (Marengo search)
    "qa_index",           # Q&A chapters rolled into one index
    "search_probe",       # pre-baked Marengo queries with their hit timecodes
    "topic_index",        # Pegasus topics/hashtags for the whole talk
    "reel_strip",         # the short-form reels cut from this talk
    "cross_talk",         # a topic this talk shares with other talks
)


def widget(kind: str, *, talk: str, session: str, wid: str, title: str,
           start: float = 0.0, end: float | None = None, category: str | None = None,
           source: str = "", confidence: float | None = None,
           body: dict | None = None, actions: list | None = None) -> dict:
    """Build one widget. `category` defaults to whatever the title classifies as."""
    if kind not in WIDGET_TYPES:
        raise ValueError(f"Unknown widget type {kind!r}; expected one of {WIDGET_TYPES}")
    title = fix_text(title)
    cat = CATEGORY_BY_ID.get(category) or categorize(title, (body or {}).get("summary", ""))
    start = round(float(start), 2)
    end = round(float(end), 2) if end is not None else None
    w = {
        "id": wid,
        "type": kind,
        "talk": talk,
        "session": session,
        "title": title,
        "category": cat["id"],
        "color": cat["color"],
        "start": start,
        "t_label": fmt_t(start),
        "source": source,
        "body": body or {},
        "actions": actions or [{"kind": "seek", "t": start}],
    }
    if end is not None:
        w["end"] = end
        w["duration"] = round(end - start, 2)
    if confidence is not None:
        w["confidence"] = round(float(confidence), 3)
    return w


def offset_widget(w: dict, delta: float) -> dict:
    """Shift a widget onto the merged timeline of a multi-part talk."""
    if not delta:
        return w
    w = json.loads(json.dumps(w))
    w["start"] = round(w["start"] + delta, 2)
    w["t_label"] = fmt_t(w["start"])
    if "end" in w:
        w["end"] = round(w["end"] + delta, 2)
    for a in w.get("actions", []):
        if a.get("kind") == "seek" and a.get("t") is not None:
            a["t"] = round(a["t"] + delta, 2)
    for key in ("segments", "items", "hits", "reels"):
        for it in w.get("body", {}).get(key, []) or []:
            for f in ("start", "end", "t"):
                if isinstance(it.get(f), (int, float)):
                    it[f] = round(it[f] + delta, 2)
            if "t_label" in it:
                it["t_label"] = fmt_t(it.get("t", it.get("start", 0)))
    return w


# --- Topic keys (cross-talk linking) ---------------------------------------
_STOP = {
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "your",
    "you", "how", "what", "why", "this", "that", "it", "is", "are", "be", "using",
    "use", "get", "make", "build", "into", "from", "at", "by", "as", "we", "i",
}


def topic_key(s: str) -> str:
    """Normalize a topic so the same idea from two speakers collides."""
    s = fix_text(s).lower()
    s = re.sub(r"[^a-z0-9+#. ]+", " ", s)
    words = [w for w in s.split() if w and w not in _STOP]
    return " ".join(words).strip()


def chapter_segments(chapters: list) -> list:
    """Normalize raw chapters into map segments (text fixed, categorized)."""
    segs = []
    for i, ch in enumerate(chapters or []):
        title = fix_text(ch.get("title") or f"Chapter {i + 1}")
        summary = fix_text(ch.get("summary") or "")
        cat = categorize(title, summary)
        segs.append({"i": i, "start": round(float(ch["start"]), 2),
                     "end": round(float(ch["end"]), 2), "t_label": fmt_t(ch["start"]),
                     "title": title, "summary": summary,
                     "category": cat["id"], "color": cat["color"]})
    segs.sort(key=lambda s: s["start"])
    return segs


def build_chapter_map(chapters, *, talk, session, wid, title, total, source):
    """The map spine itself — SPINE/ORBIT segments plus the category legend."""
    segs = chapter_segments(chapters)
    if not segs:
        return []
    counts = {}
    for s in segs:
        counts[s["category"]] = counts.get(s["category"], 0) + 1
    return [widget(
        "chapter_map", talk=talk, session=session, wid=wid, title=title,
        start=segs[0]["start"], end=segs[-1]["end"], category="concept",
        source=source,
        body={"views": ["spine", "orbit"], "total": total, "segments": segs,
              "legend": [{"id": c["id"], "label": c["label"], "color": c["color"],
                          "count": counts.get(c["id"], 0)}
                         for c in CATEGORIES if counts.get(c["id"])]},
        actions=[{"kind": "seek", "t": segs[0]["start"]}])]


def build_qa_index(chapters, *, talk, session, wid, source):
    items = [{"start": s["start"], "end": s["end"], "t_label": s["t_label"],
              "title": s["title"], "summary": s["summary"]}
             for s in chapter_segments(chapters) if s["category"] == "qa"]
    if not items:
        return []
    return [widget(
        "qa_index", talk=talk, session=session, wid=wid,
        title="Questions from the room", start=items[0]["start"],
        end=items[-1]["end"], category="qa", source=source,
        body={"items": items, "count": len(items)})]


def load_talk_chapters(talk_id: str) -> dict | None:
    """The vault's chapters for a whole talk, if they have been imported."""
    return read_json(TALK_CHAPTERS_DIR / f"{talk_id}.json")


def read_json(path: pathlib.Path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default
