#!/usr/bin/env python3
"""08 — Merge every session's widgets into one Talk Map bundle for the vault.

Reads talks/registry.json, pulls <session>/analysis/widgets.json for each mapped
session, stitches multi-part talks onto a single timeline (part 2's timecodes are
offset by part 1's runtime), links topics that recur across speakers, and writes:

    talkmap/build/talkmap.json      every talk + widget, one document
    talkmap/build/talks/<id>.json   per talk, in the vault's /api/chapters shape
                                    ({total, chapters}) plus a `widgets` array
    talkmap/build/index.html        self-contained preview of the map + widgets

The per-talk files are drop-in for recordings.organizedai.vip/vault: it already
fetches /api/chapters?video=<key> and renders SPINE/ORBIT from {total,chapters}.
Serving these adds `widgets` to that same payload — existing behaviour is
untouched, and the widget layer is additive.

    ./.venv/bin/python scripts/08_talkmap.py
    ./.venv/bin/python scripts/08_talkmap.py --strict    # fail if a talk is empty
"""
import argparse
import html
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import talkmap as T

MIN_CROSS_TALK = 2          # a topic must appear in this many talks to link them


def session_widgets(name: str) -> dict | None:
    p = T.session_dir(name) / "analysis" / "widgets.json"
    doc = T.read_json(p)
    if doc is None:
        return None
    if doc.get("schema") != T.WIDGET_SCHEMA:
        print(f"  ! {name}: unexpected schema {doc.get('schema')!r}; skipping")
        return None
    return doc


def merge_talk(talk: dict) -> dict:
    """Stitch a talk's session parts onto one timeline."""
    parts, widgets, chapters = [], [], []
    offset = 0.0
    for name in talk.get("sessions", []):
        doc = session_widgets(name)
        if doc is None:
            print(f"  · {name}: no widgets.json (run 07_widgets.py) — skipped")
            parts.append({"session": name, "present": False, "offset": round(offset, 2)})
            continue
        dur = float(doc.get("duration") or 0.0)
        for w in doc.get("widgets", []):
            shifted = T.offset_widget(w, offset)
            widgets.append(shifted)
            if shifted["type"] == "chapter_map":
                for seg in shifted["body"].get("segments", []):
                    chapters.append({"start": seg["start"], "end": seg["end"],
                                     "title": seg["title"], "summary": seg["summary"],
                                     "category": seg["category"], "color": seg["color"],
                                     "session": name})
        parts.append({"session": name, "present": True, "offset": round(offset, 2),
                      "duration": round(dur, 2), "widgets": len(doc.get("widgets", [])),
                      "video_id": doc.get("video_id"), "index_id": doc.get("index_id")})
        offset += dur
        print(f"  · {name}: {len(doc.get('widgets', []))} widgets, {dur / 60:.1f} min")

    widgets.sort(key=lambda w: (w["start"], w["id"]))
    chapters.sort(key=lambda c: c["start"])
    return {
        "id": talk["id"],
        "speaker": talk["speaker"],
        "title": talk["title"],
        "blurb": talk.get("blurb", ""),
        "workshop": talk.get("workshop", ""),
        "sessions": talk.get("sessions", []),
        "parts": parts,
        "total": round(offset, 2),
        "chapters": chapters,
        "widgets": widgets,
    }


def cross_talk_widgets(talks: list) -> list:
    """Link topics that more than one speaker covered."""
    index = {}
    for t in talks:
        for w in t["widgets"]:
            if w["type"] != "topic_index":
                continue
            for item in w["body"].get("items", []):
                key = item.get("key") or T.topic_key(item.get("name", ""))
                if not key:
                    continue
                index.setdefault(key, {})[t["id"]] = {
                    "talk": t["id"], "speaker": t["speaker"], "title": t["title"],
                    "name": item.get("name", ""),
                }
    out = []
    for key, hits in sorted(index.items()):
        if len(hits) < MIN_CROSS_TALK:
            continue
        rows = sorted(hits.values(), key=lambda r: r["talk"])
        label = rows[0]["name"] or key
        for t in talks:
            if t["id"] not in hits:
                continue
            others = [r for r in rows if r["talk"] != t["id"]]
            out.append(T.widget(
                "cross_talk", talk=t["id"], session="",
                wid=f"t{t['id']}_cross_{key.replace(' ', '-')}",
                title=f"Also covered: {label}", start=0.0, category="concept",
                source="organized-cuts:topic-index",
                body={"topic": label, "key": key,
                      "also_in": [{"talk": r["talk"], "speaker": r["speaker"],
                                   "title": r["title"],
                                   "vault_url": f"/vault?talk={r['talk']}"} for r in others]},
                actions=[]))
    return out


# --- Preview ----------------------------------------------------------------
PREVIEW_CSS = """
:root{--bg:#0c0b09;--bg2:#100f0c;--surface:#1a1814;--line:#2a2520;--muted:#605848;
--t2:#a09888;--t1:#cfc7b6;--hi:#f0ece4;--accent:#f5d623;--mono:"JetBrains Mono",ui-monospace,monospace}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--t1);font-family:system-ui,sans-serif;padding:0 0 80px}
.wrap{max-width:1180px;margin:0 auto;padding:0 22px}
header{border-bottom:1px solid var(--line);padding:18px 0;margin-bottom:34px;position:sticky;top:0;
background:rgba(12,11,9,.94);backdrop-filter:blur(8px);z-index:5}
.brand{font-family:var(--mono);font-weight:800;color:var(--hi)}.brand .y{color:var(--accent)}
.brand .sec{color:var(--muted)}
.sub{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.1em;margin-top:5px}
.talk{border:1px solid var(--line);border-radius:14px;background:var(--surface);padding:24px;margin-bottom:22px}
.talk h2{font-size:21px;color:var(--hi);letter-spacing:-.3px}
.talk .meta{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.08em;margin:7px 0 16px}
.talk .meta a{color:var(--accent);text-decoration:none}
.rail{position:relative;height:56px;background:var(--bg2);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.seg{position:absolute;top:0;bottom:0;border-right:1px solid var(--bg);cursor:default}
.seg::after{content:"";position:absolute;left:0;right:1px;bottom:0;height:4px;background:var(--c)}
.rul{display:flex;justify-content:space-between;font-family:var(--mono);font-size:9.5px;color:var(--muted);margin:5px 2px 14px}
.leg{display:flex;flex-wrap:wrap;gap:9px;margin:0 0 12px}
.pill{font-family:var(--mono);font-size:11px;border:1px solid var(--line);border-radius:20px;
padding:5px 11px;display:inline-flex;align-items:center;gap:7px}
.dot{width:8px;height:8px;border-radius:50%}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));gap:12px;margin-top:16px}
.card{background:var(--bg2);border:1px solid var(--line);border-left:3px solid var(--c);border-radius:9px;padding:14px 16px}
.card .ty{font-family:var(--mono);font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--c)}
.card .ti{color:var(--hi);font-size:14px;font-weight:600;margin:6px 0 6px;line-height:1.35}
.card .bd{font-size:12.5px;color:var(--t2);line-height:1.5}
.card .tc{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-top:9px;letter-spacing:.06em}
.card .src{font-family:var(--mono);font-size:9.5px;color:var(--muted);margin-top:4px;opacity:.8}
.empty{font-family:var(--mono);font-size:12px;color:var(--muted);padding:10px 0}
footer{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.08em;text-align:center;margin-top:40px}
"""


def render_preview(bundle: dict) -> str:
    def esc(s):
        return html.escape(str(s or ""))

    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>Talk Map Widgets // Organized AI</title>",
        f"<style>{PREVIEW_CSS}</style></head><body>",
        '<header><div class="wrap"><div class="brand">ORGANIZED <span class="y">AI</span>'
        ' <span class="sec">// TALK MAP WIDGETS</span></div>',
        f'<div class="sub">{esc(bundle["event"]["name"])} · '
        f'{len(bundle["talks"])} TALKS · {bundle["counts"]["widgets"]} WIDGETS · '
        "GENERATED FROM TWELVELABS</div></div></header>",
        '<div class="wrap">',
    ]
    for t in bundle["talks"]:
        total = t["total"] or 1
        parts.append('<section class="talk">')
        parts.append(f'<h2>{esc(t["id"])} · {esc(t["speaker"])} — {esc(t["title"])}</h2>')
        parts.append(
            f'<div class="meta">{len(t["widgets"])} WIDGETS · {len(t["chapters"])} CHAPTERS · '
            f'{total / 60:.0f} MIN · <a href="{esc(bundle["event"]["vault"])}?talk={esc(t["id"])}">'
            "OPEN IN VAULT →</a></div>")
        counts = {}
        for c in t["chapters"]:
            counts[c["category"]] = counts.get(c["category"], 0) + 1
        if counts:
            parts.append('<div class="leg">')
            for c in T.CATEGORIES:
                if counts.get(c["id"]):
                    parts.append(
                        f'<span class="pill" style="color:{c["color"]}">'
                        f'<span class="dot" style="background:{c["color"]}"></span>'
                        f'{esc(c["label"])} {counts[c["id"]]}</span>')
            parts.append("</div>")
        if t["chapters"]:
            parts.append('<div class="rail">')
            for c in t["chapters"]:
                left = c["start"] / total * 100
                width = max(c["end"] - c["start"], total * 0.004) / total * 100
                parts.append(
                    f'<div class="seg" style="--c:{c["color"]};left:{left:.3f}%;'
                    f'width:{width:.3f}%;background:color-mix(in srgb,{c["color"]} 22%,transparent)" '
                    f'title="{esc(T.fmt_t(c["start"]))} · {esc(c["title"])}"></div>')
            parts.append("</div><div class=\"rul\">")
            step = 10 if total > 2700 else 5
            m = 0
            while m <= int(total // 60):
                parts.append(f"<span>{m}:00</span>")
                m += step
            parts.append("</div>")
        if t["widgets"]:
            parts.append('<div class="cards">')
            for w in t["widgets"]:
                b = w.get("body", {})
                blurb = (b.get("caption") or b.get("text") or b.get("summary")
                         or b.get("topic") or "")
                if not blurb:
                    for key, noun in (("segments", "chapters"), ("items", "items"),
                                      ("reels", "reels")):
                        if b.get(key):
                            blurb = f"{len(b[key])} {noun}"
                            break
                parts.append(
                    f'<div class="card" style="--c:{w["color"]}">'
                    f'<div class="ty">{esc(w["type"].replace("_", " "))}</div>'
                    f'<div class="ti">{esc(w["title"])}</div>'
                    f'<div class="bd">{esc(str(blurb)[:180])}</div>'
                    f'<div class="tc">▶ {esc(w["t_label"])}'
                    + (f' · {w["duration"]:.0f}s' if w.get("duration") else "")
                    + "</div>"
                    f'<div class="src">{esc(w["source"])}</div></div>')
            parts.append("</div>")
        else:
            who = ", ".join(t["sessions"]) or "this talk's sessions"
            parts.append('<div class="empty">No widgets yet — run 07_widgets.py for '
                         f"{esc(who)}.</div>")
        parts.append("</section>")
    parts.append("</div>")
    parts.append('<footer>TALK MAP · POWERED BY TWELVELABS · CUT BY THE ORGANIZED '
                 "CUTS PIPELINE</footer></body></html>")
    return "\n".join(parts)


# --- Main -------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if any registered talk has no widgets")
    ap.add_argument("--out", default=None, help="build dir (default talkmap/build)")
    args = ap.parse_args()

    reg = T.load_registry()
    out_dir = pathlib.Path(args.out).resolve() if args.out else T.BUILD_DIR
    print(f"• Registry {T.REGISTRY_PATH}")

    talks = []
    for spec in reg["talks"]:
        print(f"• talk {spec['id']} · {spec['speaker']} — {spec['title']}")
        if not spec.get("sessions"):
            print("  · no sessions mapped — placeholder")
        talks.append(merge_talk(spec))

    cross = cross_talk_widgets(talks)
    by_talk = {}
    for w in cross:
        by_talk.setdefault(w["talk"], []).append(w)
    for t in talks:
        t["widgets"] = sorted(t["widgets"] + by_talk.get(t["id"], []),
                              key=lambda w: (w["start"], w["id"]))
    if cross:
        print(f"• {len(cross)} cross-talk links across "
              f"{len({w['body']['key'] for w in cross})} shared topics")

    bundle = {
        "schema": T.TALKMAP_SCHEMA,
        "event": reg["event"],
        "categories": [{"id": c["id"], "label": c["label"], "color": c["color"]}
                       for c in T.CATEGORIES],
        "counts": {
            "talks": len(talks),
            "with_widgets": sum(1 for t in talks if t["widgets"]),
            "chapters": sum(len(t["chapters"]) for t in talks),
            "widgets": sum(len(t["widgets"]) for t in talks),
        },
        "talks": talks,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "talks").mkdir(exist_ok=True)
    (out_dir / "talkmap.json").write_text(json.dumps(bundle, indent=2))
    for t in talks:
        # Vault-compatible: {total, chapters} is exactly what /api/chapters returns
        # today; `widgets` rides alongside it.
        (out_dir / "talks" / f"{t['id']}.json").write_text(json.dumps({
            "talk": t["id"], "speaker": t["speaker"], "title": t["title"],
            "total": t["total"], "chapters": t["chapters"], "widgets": t["widgets"],
        }, indent=2))
    (out_dir / "index.html").write_text(render_preview(bundle))

    print(f"\n  {'talk':<5} {'speaker':<10} {'chapters':>8} {'widgets':>8}  title")
    print("  " + "-" * 66)
    for t in talks:
        print(f"  {t['id']:<5} {t['speaker']:<10} {len(t['chapters']):>8} "
              f"{len(t['widgets']):>8}  {t['title'][:30]}")
    c = bundle["counts"]
    print(f"\n✓ {c['widgets']} widgets across {c['with_widgets']}/{c['talks']} talks "
          f"-> {out_dir}")
    print(f"  preview: {out_dir / 'index.html'}")

    if args.strict:
        empty = [t["id"] for t in talks if not t["widgets"]]
        if empty:
            print(f"\nERROR: talks with no widgets: {', '.join(empty)}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
