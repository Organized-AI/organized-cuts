#!/usr/bin/env python3
"""Import the vault's own Talk Map into the pipeline.

recordings.organizedai.vip serves the videos and the Talk Map from behind a
login: /api/videos lists the recordings, /api/chapters?video=<key> returns the
TwelveLabs chapters the SPINE/ORBIT map is drawn from. Both are 401 without a
session cookie, so this stage takes an export rather than calling them.

Given that export it does two things:

  1. Reconciles the vault's recordings against talks/registry.json — the vault is
     the authority on which recordings belong to which talk, so this is what
     settles a mapping instead of guessing from directory names.
  2. Writes each session's analysis/chapters.json from the vault's chapters, so
     07_widgets.py builds the widget layer on the map that is already live
     instead of asking Pegasus for a second, slightly different opinion.

Produce the export from a logged-in browser tab on the vault:

    copy(await (async () => {
      const {videos} = await (await fetch("/api/videos")).json();
      const chapters = {};
      for (const v of videos)
        chapters[v.key] = await (await fetch(
          "/api/chapters?video=" + encodeURIComponent(v.key))).json();
      return JSON.stringify({videos, chapters}, null, 2);
    })())

Then:

    ./.venv/bin/python scripts/import_talkmap.py vault-export.json           # report only
    ./.venv/bin/python scripts/import_talkmap.py vault-export.json --write   # apply
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import talkmap as T

# The vault selects a talk with `v.key.startsWith(want + " ")`, so the leading
# two-digit token of a recording key is its talk id.
KEY_TALK_RX = re.compile(r"^\s*(\d{2})\s")


def talk_of(key: str) -> str | None:
    m = KEY_TALK_RX.match(key or "")
    return m.group(1) if m else None


def load_export(path: pathlib.Path) -> tuple[list, dict]:
    """Accept either export shape.

    Full:    {"videos": [{key,title,size}], "chapters": {key: {total,chapters}}}
    Compact: [{"key": ..., "total": ..., "chapters": [...]}, ...]

    The compact form is what the one-liner in the module docstring produces; it
    carries everything the map needs and is small enough to paste.
    """
    doc = json.loads(path.read_text())
    if isinstance(doc, list):
        rows = [r for r in doc if r.get("key")]
        if not rows:
            raise SystemExit(f"{path}: list export has no rows with a `key`.")
        return ([{"key": r["key"], "title": r.get("title") or r["key"]} for r in rows],
                {r["key"]: r for r in rows})
    videos = doc.get("videos")
    if videos is None:
        raise SystemExit(
            f"{path}: no `videos` array and not a list export — expected the "
            "output of the console snippet, not the snippet itself.")
    chapters = doc.get("chapters") or {}
    if isinstance(chapters, list):
        chapters = {c["key"]: c for c in chapters if c.get("key")}
    return videos, chapters


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", type=pathlib.Path, help="vault export JSON")
    ap.add_argument("--write", action="store_true",
                    help="write talks/chapters/<id>.json (default: report only)")
    args = ap.parse_args()

    videos, chapters = load_export(args.export)
    reg = T.load_registry()
    by_talk = {t["id"]: t for t in reg["talks"]}

    print(f"\u2022 {len(videos)} recordings in the export, "
          f"{len(chapters)} with chapters")

    wrote, problems = 0, []
    seen = set()
    for v in sorted(videos, key=lambda v: v.get("key", "")):
        key = v.get("key") or ""
        tid = talk_of(key)
        if not tid:
            problems.append(f"{key!r} has no NN talk prefix — skipped")
            continue
        talk = by_talk.get(tid)
        if not talk:
            problems.append(f"talk {tid} ({key!r}) is on the vault but not in the registry")
            continue
        if tid in seen:
            problems.append(f"talk {tid} has more than one recording; "
                            "the talk-level chapter file keeps the first")
            continue
        seen.add(tid)

        doc = chapters.get(key) or {}
        chs = doc.get("chapters") or []
        sessions = talk.get("sessions", [])
        print(f"\n\u2022 talk {tid} \u00b7 {talk['speaker']} \u2014 {talk['title']}")
        print(f"    vault:    {key}  ({len(chs)} chapters, "
              f"{(doc.get('total') or 0) / 60:.0f} min)")
        print(f"    sessions: {', '.join(sessions) if sessions else '(none in this repo)'}")
        if not chs:
            problems.append(f"talk {tid}: no chapters in the export for {key!r}")
            print("    ! no chapters — skipped")
            continue

        segs = T.chapter_segments(chs)
        counts = {}
        for sg in segs:
            counts[sg["category"]] = counts.get(sg["category"], 0) + 1
        print("    map:      " + ", ".join(
            f"{T.CATEGORY_BY_ID[c]['label']} {n}" for c, n in counts.items()))

        payload = {"talk": tid, "total": doc.get("total") or segs[-1]["end"],
                   "chapters": chs,
                   "imported_from": {"vault_key": key, "title": v.get("title"),
                                     "endpoint": "/api/chapters"}}
        out = T.TALK_CHAPTERS_DIR / f"{tid}.json"
        if args.write:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, indent=2))
        wrote += 1
        print(f"    {'wrote' if args.write else 'would write'} -> "
              f"talks/chapters/{tid}.json")

    missing = [t["id"] for t in reg["talks"] if t["id"] not in seen]
    if missing:
        problems.append("no vault recording for talk(s): " + ", ".join(missing))

    mark = "\u2713" if args.write else "\u00b7"
    state = "imported" if args.write else "ready (dry run)"
    print(f"\n{mark} {wrote} talk map(s) {state}")
    if problems:
        print("\nNotes:")
        for p_ in problems:
            print(f"  - {p_}")
    if not args.write and wrote:
        print("\nRe-run with --write to apply, then: "
              "bash scripts/widgets_all.sh --offline")


if __name__ == "__main__":
    main()
