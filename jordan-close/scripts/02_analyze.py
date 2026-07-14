#!/usr/bin/env python3
"""02 — Build clip candidates from TwelveLabs and write analysis/clips.json.

Sources, merged and de-duped:
  • Generative (Pegasus): highlights + chapters via analyze().
  • Embedding search (Marengo): 5 intent queries via search.query().
Candidates are snapped to transcript sentence boundaries, held to 20-45s,
de-duped by temporal overlap, and each gets a Pegasus-written hook + caption.

    ./.venv/bin/python scripts/02_analyze.py
"""
import json
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C

client = None
INDEX_ID = None
VIDEO_ID = None


def extract_json(text: str):
    """Pull the first JSON object/array out of an LLM text response."""
    if not text:
        return None
    text = text.strip()
    # strip ```json fences
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
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


def analyze_text(prompt, start=None, end=None, temperature=0.2, max_tokens=2000):
    kw = dict(model_name=C.GENERATIVE_MODEL, video_id=VIDEO_ID, prompt=prompt,
              temperature=temperature, max_tokens=max_tokens)
    if start is not None:
        kw["start_time"] = float(start)
    if end is not None:
        kw["end_time"] = float(end)
    res = C.dump(client.analyze(**kw))
    return res.get("data") or ""


def get_transcript():
    try:
        v = C.dump(client.indexes.videos.retrieve(INDEX_ID, VIDEO_ID, transcription=True))
    except Exception as e:
        print(f"  ! transcript fetch failed ({e}); snapping disabled.")
        return []
    segs = v.get("transcription") or []
    out = []
    for s in segs:
        s = C.dump(s)
        st, en = s.get("start"), s.get("end")
        val = s.get("value") or s.get("text") or ""
        if st is not None and en is not None:
            out.append({"start": float(st), "end": float(en), "text": val.strip()})
    return sorted(out, key=lambda x: x["start"])


def text_between(segs, s, e):
    return " ".join(x["text"] for x in segs if x["end"] > s and x["start"] < e).strip()


def snap_clip(s, e, segs):
    s, e = float(s), float(e)
    if not segs:
        d = max(C.CLIP_MIN_S, min(C.CLIP_MAX_S, e - s))
        return round(s, 2), round(s + d, 2)
    starts = sorted({x["start"] for x in segs})
    ends = sorted({x["end"] for x in segs})
    ns = min(starts, key=lambda x: abs(x - s))
    cands = [en for en in ends if ns + C.CLIP_MIN_S <= en <= ns + C.CLIP_MAX_S]
    if cands:
        ne = min(cands, key=lambda x: abs(x - e))
    else:
        ne = ns + max(C.CLIP_MIN_S, min(C.CLIP_MAX_S, e - s))
    return round(ns, 2), round(ne, 2)


def iou(a, b):
    inter = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    union = (a["end"] - a["start"]) + (b["end"] - b["start"]) - inter
    return inter / union if union > 0 else 0.0


def classify_kind(clip, transcript_txt):
    """demo -> cut to the ISO2 screen feed; talk -> presenter only.
    Only ISO1 (the presenter) is in TwelveLabs, so we infer screen moments from
    the search intent and spoken references to the screen."""
    if not C.ISO2_PRESENT:
        return "talk"
    if clip.get("query") == C.DEMO_QUERY:
        return "demo"
    hay = f"{clip.get('query','')} {clip.get('note','')} {transcript_txt}".lower()
    if any(k in hay for k in C.DEMO_KEYWORDS):
        return "demo"
    return "talk"


# --- Candidate sources ------------------------------------------------------
def generative_candidates():
    prompt = (
        "You are a short-form video editor. From this talk, identify the most "
        "shareable moments. Return ONLY JSON of the form "
        '{"highlights":[{"start":<sec>,"end":<sec>,"title":"...","reason":"..."}],'
        '"chapters":[{"start":<sec>,"end":<sec>,"title":"..."}]}. '
        "Give 8-12 highlights, each 15-60s, using real timestamps in seconds."
    )
    data = analyze_text(prompt, max_tokens=4000)
    parsed = extract_json(data) or {}
    out = []
    for h in parsed.get("highlights", []):
        if h.get("start") is None or h.get("end") is None:
            continue
        out.append({"start": float(h["start"]), "end": float(h["end"]),
                    "score": 0.85, "source": "highlight",
                    "note": h.get("title") or h.get("reason") or ""})
    for ch in parsed.get("chapters", []):
        if ch.get("start") is None or ch.get("end") is None:
            continue
        out.append({"start": float(ch["start"]), "end": float(ch["end"]),
                    "score": 0.6, "source": "chapter", "note": ch.get("title") or ""})
    print(f"  generative: {len(out)} raw (highlights+chapters)")
    return out


def search_candidates():
    out = []
    for q in C.SEARCH_QUERIES:
        try:
            pager = client.search.query(
                index_id=INDEX_ID,
                search_options=["visual", "audio"],
                query_text=q,
                group_by="clip",
                page_limit=5,
            )
        except Exception as e:
            print(f"  ! search '{q}' failed: {e}")
            continue
        n = 0
        for item in pager:
            d = C.dump(item)
            st, en = d.get("start"), d.get("end")
            if st is None or en is None:
                continue
            score = d.get("score")
            if score is None:  # newer SDK may only surface rank/confidence
                conf = d.get("confidence")
                score = {"high": 0.9, "medium": 0.7, "low": 0.5}.get(conf, 0.75)
            out.append({"start": float(st), "end": float(en), "score": float(score),
                        "source": "search", "note": q})
            n += 1
            if n >= 5:
                break
        print(f"  search '{q}': {n} hits")
    return out


def main():
    global client, INDEX_ID, VIDEO_ID
    st = C.require_state("index_id", "video_id")
    INDEX_ID, VIDEO_ID = st["index_id"], st["video_id"]
    client = C.client()

    print("• Fetching transcript…")
    segs = get_transcript()
    print(f"  {len(segs)} transcript segments")

    print("• Generative highlights + chapters…")
    cands = generative_candidates()
    print("• Embedding search…")
    cands += search_candidates()
    if not cands:
        C.die("No candidates produced by generative or search steps.")

    # Snap + clamp
    for c in cands:
        c["start"], c["end"] = snap_clip(c["start"], c["end"], segs)
    cands = [c for c in cands if c["end"] - c["start"] >= C.CLIP_MIN_S - 1]

    # De-dupe by overlap, keep higher score
    cands.sort(key=lambda c: c["score"], reverse=True)
    kept = []
    for c in cands:
        if all(iou(c, k) < 0.5 for k in kept):
            kept.append(c)
    kept.sort(key=lambda c: c["start"])

    lo, hi = C.CLIP_TARGET_COUNT
    if len(kept) > hi:
        kept = sorted(kept, key=lambda c: c["score"], reverse=True)[:hi]
        kept.sort(key=lambda c: c["start"])
    print(f"• {len(kept)} candidates after de-dupe (target {lo}-{hi})")

    # Hook + caption per clip
    clips = []
    for i, c in enumerate(kept, 1):
        cid = f"{i:02d}"
        transcript_txt = text_between(segs, c["start"], c["end"])
        prompt = (
            "Write short-form social copy for this exact video segment. Return ONLY "
            'JSON {"hook":"<=8 word scroll-stopping on-screen hook",'
            '"caption":"1-2 sentence caption with 2-3 relevant hashtags"}. '
            f"Segment context: {transcript_txt[:600] or c.get('note','')}"
        )
        hook, caption = "", ""
        # NB: start_time/end_time are pegasus1.5-only; the prompt carries the
        # segment transcript, so whole-video analyze is enough here.
        try:
            parsed = extract_json(analyze_text(prompt, max_tokens=400))
        except Exception as e:
            print(f"    ! copy gen failed for {cid} ({e}); using transcript fallback")
            parsed = None
        if isinstance(parsed, dict):
            hook = (parsed.get("hook") or "").strip()
            caption = (parsed.get("caption") or "").strip()
        if not hook:
            hook = (c.get("note") or transcript_txt[:60]).strip()
        if not caption:
            caption = transcript_txt[:180].strip()
        clip = {
            "id": cid,
            "start": c["start"],
            "end": c["end"],
            "duration": round(c["end"] - c["start"], 2),
            "hook": hook,
            "caption": caption,
            "score": round(c["score"], 3),
            "source": c["source"],
            "query": c.get("note", ""),
            "transcript": transcript_txt,
        }
        clip["kind"] = classify_kind(clip, transcript_txt)
        clips.append(clip)
        print(f"  [{cid}] {c['start']:.1f}-{c['end']:.1f}s ({clip['duration']:.0f}s) [{clip['kind']}] {hook!r}")

    C.ANALYSIS.mkdir(parents=True, exist_ok=True)
    C.CLIPS_PATH.write_text(json.dumps({"video_id": VIDEO_ID, "clips": clips}, indent=2))
    print(f"\n✓ Wrote {len(clips)} clips -> {C.CLIPS_PATH}")


if __name__ == "__main__":
    main()
