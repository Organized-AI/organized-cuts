#!/usr/bin/env python3
"""07 — Turn one session's TwelveLabs analysis into Talk Map widgets.

Everything a widget shows traces back to something TwelveLabs indexed, analyzed
or determined for this asset:

  Pegasus chapters   -> chapter_map, qa_index          (the map spine)
  Pegasus highlights -> moment, demo_walkthrough        (clips.json `source`)
  Pegasus gist       -> topic_index                     (topics + hashtags)
  Marengo search     -> search_probe, quote, takeaway   (clips.json `query`)
  Cut reels          -> reel_strip                      (reels/manifest.json)

Writes <session>/analysis/widgets.json. Network responses are cached next to it
(chapters.json, topics.json, probes.json) so re-runs cost nothing.

No video files are read at any point — not the ProRes masters, not the proxy.
This stage needs the TwelveLabs index (already analyzed) and whatever local
analysis JSON exists. If state.json is missing, the index and video ids are
resolved by index name rather than re-uploading anything.

    ./.venv/bin/python scripts/07_widgets.py                 # live: fills gaps from TwelveLabs
    ./.venv/bin/python scripts/07_widgets.py --offline       # local artifacts only
    OC_PROJECT_DIR=../session-2-ct ./.venv/bin/python scripts/07_widgets.py
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C
from lib import talkmap as T

# Marengo probes offered as one-click "search inside this talk" entry points.
# The first five are the pipeline's own clip-finding queries (02_analyze.py), so
# the widget surfaces exactly what the cuts were chosen from; the rest are the
# questions an audience actually asks of a workshop recording.
PROBE_QUERIES = list(C.SEARCH_QUERIES) + [
    "what does this cost to run",
    "the tool or platform being used",
    "a question from the audience",
    "a mistake, gotcha, or warning",
]
QUOTE_QUERY = "quotable one-liner"
TAKEAWAY_QUERY = "actionable takeaway builders can use"

MAX_QUOTES = 4
MAX_TAKEAWAYS = 4
MAX_PROBE_HITS = 4


# --- Local artifacts --------------------------------------------------------
def load_clips() -> list:
    d = T.read_json(C.CLIPS_PATH, {}) or {}
    return d.get("clips", [])


def load_manifest() -> dict:
    d = T.read_json(C.MANIFEST_PATH, {}) or {}
    return {c["id"]: c for c in d.get("clips", [])}


def load_transcript() -> list:
    """analysis/transcript.json is a flat list of {start,end,text} words."""
    d = T.read_json(C.ANALYSIS / "transcript.json", []) or []
    return d if isinstance(d, list) else []


def words_between(words: list, s: float, e: float, limit: int = 320) -> str:
    txt = " ".join(w["text"] for w in words if w.get("end", 0) > s and w.get("start", 0) < e)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:limit].strip()


# --- TwelveLabs (cached) ----------------------------------------------------
def cached(name: str, builder, offline: bool):
    """Return analysis/<name>.json, building it via TwelveLabs when absent."""
    path = C.ANALYSIS / name
    hit = T.read_json(path)
    if hit is not None:
        print(f"  · {name} (cached)")
        return hit
    if offline:
        print(f"  · {name} unavailable (offline)")
        return None
    try:
        val = builder()
    except Exception as e:
        print(f"  ! {name} fetch failed: {e}")
        return None
    if val is None:
        return None
    C.ANALYSIS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(val, indent=2))
    print(f"  · {name} fetched -> {path.name}")
    return val


def extract_json(text: str):
    """Same salvage as 02_analyze.py: LLM prose may wrap the JSON."""
    if not text:
        return None
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    for opn, cls in (("{", "}"), ("[", "]")):
        i, j = text.find(opn), text.rfind(cls)
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except Exception:
                continue
    return None


class TL:
    """Lazy TwelveLabs client bound to this session's index/video."""

    def __init__(self, offline: bool):
        self.offline = offline
        self._c = None
        st = T.read_json(C.STATE_PATH, {}) or {}
        self.index_id, self.video_id = st.get("index_id"), st.get("video_id")

    def resolve(self) -> bool:
        """Recover index_id/video_id from TwelveLabs by index name.

        state.json lives under the gitignored analysis/ dir, so a machine that
        did not run 01_ingest has no pointer to an already-indexed asset. The
        index name is in project.json and is stable, so look the ids up rather
        than re-uploading anything.
        """
        try:
            if not self.index_id:
                for idx in self.client.indexes.list():
                    d = C.dump(idx)
                    if d.get("index_name") == C.INDEX_NAME:
                        self.index_id = d.get("id") or d.get("_id")
                        break
                if not self.index_id:
                    print(f"  ! no TwelveLabs index named {C.INDEX_NAME!r}")
                    return False
                print(f"  · resolved index {C.INDEX_NAME!r} -> {self.index_id}")
            if not self.video_id:
                vids = [C.dump(v) for v in self.client.indexes.videos.list(self.index_id)]
                if not vids:
                    print(f"  ! index {self.index_id} has no videos")
                    return False
                if len(vids) > 1:
                    print(f"  · {len(vids)} videos in the index; using the first")
                self.video_id = vids[0].get("id") or vids[0].get("_id")
                print(f"  · resolved video -> {self.video_id}")
        except Exception as e:
            print(f"  ! resolve failed: {e}")
            return False
        C.save_state(index_id=self.index_id, video_id=self.video_id)
        return True

    @property
    def client(self):
        if self._c is None:
            self._c = C.client()
        return self._c

    @property
    def ready(self) -> bool:
        return bool(self.index_id and self.video_id and not self.offline)

    def analyze_text(self, prompt: str, max_tokens: int = 4000) -> str:
        res = C.dump(self.client.analyze(
            model_name=C.GENERATIVE_MODEL, video_id=self.video_id,
            prompt=prompt, temperature=0.2, max_tokens=max_tokens))
        return res.get("data") or ""

    def duration(self):
        if not self.ready:
            return None
        try:
            v = C.dump(self.client.indexes.videos.retrieve(self.index_id, self.video_id))
        except Exception as e:
            print(f"  ! duration fetch failed: {e}")
            return None
        meta = C.dump(v.get("system_metadata") or {}) or {}
        return meta.get("duration")

    def chapters(self):
        """Pegasus chapters — the same signal the vault's /api/chapters serves."""
        prompt = (
            "Segment this talk into sequential chapters covering the whole runtime. "
            'Return ONLY JSON {"chapters":[{"start":<sec>,"end":<sec>,"title":"...",'
            '"summary":"one sentence"}]}. Titles must be 2-6 words and name the '
            "actual subject. Use real timestamps in seconds; do not overlap."
        )
        parsed = extract_json(self.analyze_text(prompt)) or {}
        rows = parsed.get("chapters") if isinstance(parsed, dict) else parsed
        out = []
        for ch in rows or []:
            if ch.get("start") is None or ch.get("end") is None:
                continue
            out.append({"start": round(float(ch["start"]), 2),
                        "end": round(float(ch["end"]), 2),
                        "title": (ch.get("title") or "").strip(),
                        "summary": (ch.get("summary") or "").strip()})
        out.sort(key=lambda c: c["start"])
        return {"chapters": out} if out else None

    def topics(self):
        """Pegasus gist: topics + hashtags for the asset as a whole."""
        try:
            g = C.dump(self.client.gist(video_id=self.video_id,
                                        types=["topic", "hashtag", "title"]))
            topics = [str(t) for t in (g.get("topics") or [])]
            tags = [str(h).lstrip("#") for h in (g.get("hashtags") or [])]
            title = g.get("title") or ""
            if topics or tags:
                return {"title": title, "topics": topics, "hashtags": tags}
        except Exception as e:
            print(f"  · gist unavailable ({e}); falling back to analyze()")
        prompt = (
            "List what this talk actually covers. Return ONLY JSON "
            '{"title":"...","topics":["..."],"hashtags":["..."]} with 6-10 topics '
            "(2-4 words each, concrete tools/concepts named on stage) and 5-8 hashtags."
        )
        parsed = extract_json(self.analyze_text(prompt, max_tokens=800))
        if not isinstance(parsed, dict):
            return None
        return {"title": (parsed.get("title") or "").strip(),
                "topics": [str(t) for t in (parsed.get("topics") or [])],
                "hashtags": [str(h).lstrip("#") for h in (parsed.get("hashtags") or [])]}

    def probes(self):
        """Run every probe query through Marengo, keep the top hits."""
        out = {}
        for q in PROBE_QUERIES:
            hits = []
            try:
                pager = self.client.search.query(
                    index_id=self.index_id, search_options=["visual", "audio"],
                    query_text=q, group_by="clip", page_limit=MAX_PROBE_HITS)
            except Exception as e:
                print(f"  ! probe {q!r} failed: {e}")
                out[q] = []
                continue
            for item in pager:
                d = C.dump(item)
                if d.get("start") is None:
                    continue
                score = d.get("score")
                if score is None:
                    score = {"high": 0.9, "medium": 0.7, "low": 0.5}.get(d.get("confidence"), 0.75)
                hits.append({"start": round(float(d["start"]), 2),
                             "end": round(float(d.get("end") or d["start"]), 2),
                             "score": round(float(score), 3),
                             "confidence": d.get("confidence") or ""})
                if len(hits) >= MAX_PROBE_HITS:
                    break
            out[q] = hits
            print(f"  · probe {q!r}: {len(hits)} hits")
        return out


# --- Widget builders --------------------------------------------------------
def w_chapter_map(ctx, chapters):
    return T.build_chapter_map(
        chapters, talk=ctx["talk"], session=ctx["session"],
        wid=f"{ctx['prefix']}_map", title=f"{ctx['speaker']} — Talk Map",
        total=ctx["duration"], source=ctx["chapter_source"])


def w_qa_index(ctx, chapters):
    return T.build_qa_index(
        chapters, talk=ctx["talk"], session=ctx["session"],
        wid=f"{ctx['prefix']}_qa", source=ctx["chapter_source"])


def w_moments(ctx, clips, manifest):
    """One widget per Pegasus highlight, linked to its cut reel when there is one."""
    out = []
    for c in clips:
        if c.get("source") not in ("highlight", "chapter"):
            continue
        if c.get("kind") == "demo":
            continue                     # rendered as demo_walkthrough instead
        m = manifest.get(c["id"], {})
        out.append(T.widget(
            "moment", talk=ctx["talk"], session=ctx["session"],
            wid=f"{ctx['prefix']}_moment_{c['id']}", title=c.get("hook") or "Highlight",
            start=c["start"], end=c["end"], confidence=c.get("score"),
            source=f"twelvelabs:pegasus.{c.get('source', 'highlight')}",
            body={"caption": T.fix_text(c.get("caption") or ""),
                  "transcript": T.fix_text(c.get("transcript") or "")[:400],
                  "note": T.fix_text(c.get("query") or ""),
                  "clip_id": c["id"],
                  "reel": m.get("reel"), "treatment": m.get("treatment"),
                  "tc_in": T.fmt_tc(c["start"]), "tc_out": T.fmt_tc(c["end"])}))
    return out


def w_demos(ctx, clips, manifest):
    out = []
    for c in clips:
        if c.get("kind") != "demo":
            continue
        m = manifest.get(c["id"], {})
        out.append(T.widget(
            "demo_walkthrough", talk=ctx["talk"], session=ctx["session"],
            wid=f"{ctx['prefix']}_demo_{c['id']}", title=c.get("hook") or "Live demo",
            start=c["start"], end=c["end"], category="demo", confidence=c.get("score"),
            source=f"twelvelabs:{'marengo.search' if c.get('source') == 'search' else 'pegasus.' + str(c.get('source'))}",
            body={"caption": T.fix_text(c.get("caption") or ""),
                  "transcript": T.fix_text(c.get("transcript") or "")[:400],
                  "screen_feed": "ISO2" in (m.get("sources") or []),
                  "treatment": m.get("treatment"), "reel": m.get("reel"),
                  "clip_id": c["id"],
                  "tc_in": T.fmt_tc(c["start"]), "tc_out": T.fmt_tc(c["end"])}))
    return out


def _from_query(ctx, clips, words, query, kind, cat, limit, label):
    """Clips that Marengo returned for `query`, rendered as quote/takeaway cards."""
    picked = [c for c in clips
              if c.get("source") == "search" and (c.get("query") or "").lower() == query]
    picked.sort(key=lambda c: c.get("score", 0), reverse=True)
    out = []
    for c in picked[:limit]:
        text = T.fix_text(c.get("transcript") or "") or words_between(words, c["start"], c["end"])
        if not text:
            continue
        out.append(T.widget(
            kind, talk=ctx["talk"], session=ctx["session"],
            wid=f"{ctx['prefix']}_{kind}_{c['id']}",
            title=c.get("hook") or label, start=c["start"], end=c["end"],
            category=cat, confidence=c.get("score"), source="twelvelabs:marengo.search",
            body={"text": text[:320], "speaker": ctx["speaker"],
                  "query": query, "clip_id": c["id"],
                  "caption": T.fix_text(c.get("caption") or "")}))
    return out


def w_probes(ctx, probes, chapters):
    if not probes:
        return []
    def chapter_at(t):
        for ch in chapters or []:
            if ch["start"] <= t < ch["end"]:
                return T.fix_text(ch.get("title") or "")
        return ""
    items = []
    for q, hits in probes.items():
        if not hits:
            continue
        items.append({"query": q, "hits": [
            {"t": h["start"], "end": h.get("end"), "t_label": T.fmt_t(h["start"]),
             "score": h.get("score"), "strong": (h.get("score") or 0) >= 0.8,
             "chapter": chapter_at(h["start"])}
            for h in hits]})
    if not items:
        return []
    return [T.widget(
        "search_probe", talk=ctx["talk"], session=ctx["session"],
        wid=f"{ctx['prefix']}_probes", title="Search inside this talk",
        start=0.0, end=ctx["duration"], category="tools",
        source="twelvelabs:marengo.search",
        body={"items": items,
              "placeholder": "search inside this talk — e.g. 'pricing', 'live demo', 'MCP'"},
        actions=[{"kind": "search", "endpoint": "/api/search"}])]


def w_topics(ctx, topics):
    if not topics:
        return []
    names = [T.fix_text(t) for t in (topics.get("topics") or []) if str(t).strip()]
    if not names:
        return []
    return [T.widget(
        "topic_index", talk=ctx["talk"], session=ctx["session"],
        wid=f"{ctx['prefix']}_topics", title="What this talk covers",
        start=0.0, end=ctx["duration"], category="concept",
        source="twelvelabs:pegasus.gist",
        body={"items": [{"name": n, "key": T.topic_key(n)} for n in names],
              "hashtags": [T.fix_text(h) for h in (topics.get("hashtags") or [])],
              "model_title": T.fix_text(topics.get("title") or "")},
        actions=[])]


def w_reels(ctx, clips, manifest):
    reels = []
    for c in clips:
        m = manifest.get(c["id"])
        if not m or not m.get("reel"):
            continue
        reels.append({"clip_id": c["id"], "start": c["start"], "end": c["end"],
                      "t_label": T.fmt_t(c["start"]), "duration": c.get("duration"),
                      "hook": T.fix_text(c.get("hook") or ""),
                      "caption": T.fix_text(c.get("caption") or ""),
                      "kind": m.get("kind"), "reel": m.get("reel"),
                      "treatment": m.get("treatment")})
    if not reels:
        return []
    return [T.widget(
        "reel_strip", talk=ctx["talk"], session=ctx["session"],
        wid=f"{ctx['prefix']}_reels", title=f"{len(reels)} reels cut from this talk",
        start=reels[0]["start"], end=reels[-1]["end"], category="demo",
        source="organized-cuts:reels/manifest.json",
        body={"reels": reels, "count": len(reels),
              "demos": sum(1 for r in reels if r["kind"] == "demo")},
        actions=[])]


# --- Main -------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true",
                    help="build only from local artifacts; never call TwelveLabs")
    ap.add_argument("--refresh", action="store_true",
                    help="discard cached chapters/topics/probes and re-fetch")
    args = ap.parse_args()

    session = C.CFG.get("name") or C.PROJECT_DIR.name
    reg = T.load_registry()
    talk = T.talk_for_session(session, reg)
    if not talk:
        C.die(f"Session {session!r} is not mapped to a talk in {T.REGISTRY_PATH}.\n"
              "  Add it to a talk's `sessions` list (or fix the session name) and re-run.")

    print(f"• {session} -> talk {talk['id']} · {talk['speaker']} — {talk['title']}")
    if args.refresh:
        for n in ("chapters.json", "topics.json", "probes.json"):
            p = C.ANALYSIS / n
            if p.exists():
                p.unlink()
                print(f"  · dropped cached {n}")

    tl = TL(args.offline)
    if not args.offline and not (tl.index_id and tl.video_id):
        print(f"  · no index/video in state.json — resolving {C.INDEX_NAME!r} from TwelveLabs")
        if not tl.resolve():
            print("  ! could not resolve the indexed asset — continuing offline")
            tl.offline = True

    clips = load_clips()
    manifest = load_manifest()
    words = load_transcript()
    print(f"  · {len(clips)} clips, {len(manifest)} reels, {len(words)} transcript words")

    ch_doc = cached("chapters.json", tl.chapters, tl.offline) or {}
    chapters = ch_doc.get("chapters") or []
    topics = cached("topics.json", tl.topics, tl.offline)
    probes = cached("probes.json", tl.probes, tl.offline)

    duration = ch_doc.get("total") or (chapters[-1]["end"] if chapters else 0.0)
    if not duration:
        duration = tl.duration() or (max((c["end"] for c in clips), default=0.0))
    duration = round(float(duration or 0.0), 2)

    ctx = {"talk": talk["id"], "session": session, "speaker": talk["speaker"],
           "prefix": f"t{talk['id']}_{session}", "duration": duration,
           "chapter_source": ("vault:/api/chapters" if ch_doc.get("imported_from")
                              else "twelvelabs:pegasus.chapters")}

    widgets = []
    widgets += w_chapter_map(ctx, chapters)
    widgets += w_topics(ctx, topics)
    widgets += w_probes(ctx, probes, chapters)
    widgets += w_moments(ctx, clips, manifest)
    widgets += w_demos(ctx, clips, manifest)
    widgets += _from_query(ctx, clips, words, QUOTE_QUERY, "quote", "concept",
                           MAX_QUOTES, "Quote")
    widgets += _from_query(ctx, clips, words, TAKEAWAY_QUERY, "takeaway", "tools",
                           MAX_TAKEAWAYS, "Takeaway")
    widgets += w_qa_index(ctx, chapters)
    widgets += w_reels(ctx, clips, manifest)
    widgets.sort(key=lambda w: (w["start"], w["id"]))

    doc = {
        "schema": T.WIDGET_SCHEMA,
        "session": session,
        "talk": talk["id"],
        "speaker": talk["speaker"],
        "talk_title": talk["title"],
        "index_id": tl.index_id,
        "video_id": tl.video_id,
        "duration": duration,
        "categories": [{"id": c["id"], "label": c["label"], "color": c["color"]}
                       for c in T.CATEGORIES],
        "inputs": {"chapters": len(chapters), "clips": len(clips),
                   "reels": len(manifest), "transcript_words": len(words),
                   "topics": bool(topics), "probes": bool(probes),
                   "offline": bool(tl.offline)},
        "widgets": widgets,
    }
    C.ANALYSIS.mkdir(parents=True, exist_ok=True)
    out = C.ANALYSIS / "widgets.json"
    out.write_text(json.dumps(doc, indent=2))

    by_type = {}
    for w in widgets:
        by_type[w["type"]] = by_type.get(w["type"], 0) + 1
    print(f"\n  {'type':<18} n")
    print("  " + "-" * 24)
    for k in T.WIDGET_TYPES:
        if by_type.get(k):
            print(f"  {k:<18} {by_type[k]}")
    print(f"\n✓ {len(widgets)} widgets -> {out}")
    if not widgets:
        print("  (nothing to build — run 02_analyze.py, or pass --refresh with a "
              "TwelveLabs key to fetch chapters)")


if __name__ == "__main__":
    main()
