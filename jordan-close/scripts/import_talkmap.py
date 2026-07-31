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
    doc = json.loads(path.read_text())
    videos = doc.get("videos")
    if videos is None:
        raise SystemExit(f"{path}: no `videos` array — is this a /api/videos export?")
    chapters = doc.get("chapters") or {}
    # Tolerate the list form: [{key, total, chapters}, ...]
    if isinstance(chapters, list):
        chapters = {c["key"]: c for c in chapters if c.get("key")}
    return videos, chapters


def parse_map(pairs: list) -> dict:
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise SystemExit(f"--map expects '<video key>=<session>', got {p!r}")
        k, s = p.split("=", 1)
        out[k.strip()] = s.strip()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", type=pathlib.Path, help="vault export JSON")
    ap.add_argument("--write", action="store_true",
                    help="write analysis/chapters.json (default: report only)")
    ap.add_argument("--map", action="append", default=[], metavar="KEY=SESSION",
                    help="pair one recording with one session; repeatable")
    args = ap.parse_args()

    videos, chapters = load_export(args.export)
    reg = T.load_registry()
    by_talk = {t["id"]: t for t in reg["talks"]}
    explicit = parse_map(args.map)

    # Group the vault's recordings by the talk id in their key.
    vault: dict[str, list] = {}
    orphan = []
    for v in videos:
        tid = talk_of(v.get("key") or "")
        if tid:
            vault.setdefault(tid, []).append(v)
        else:
            orphan.append(v)
    for tid in vault:
        vault[tid].sort(key=lambda v: v.get("key", ""))

    print(f"• {len(videos)} recordings in the export, "
          f"{len(chapters)} with chapters")
    if orphan:
        print(f"  ! {len(orphan)} recordings have no NN talk prefix: "
              + ", ".join(repr(v.get('key')) for v in orphan[:4]))

    pairs, problems = [], []
    for tid in sorted(set(vault) | set(by_talk)):
        recs = vault.get(tid, [])
        talk = by_talk.get(tid)
        sessions = list(talk["sessions"]) if talk else []
        label = f"talk {tid}" + (f" · {talk['speaker']}" if talk else " (not in registry)")
        print(f"\n• {label}")
        if not talk:
            problems.append(f"talk {tid} is on the vault but absent from the registry")
            for v in recs:
                print(f"    vault: {v.get('key')}")
            continue
        for v in recs:
            print(f"    vault:    {v.get('key')}")
        for s in sessions:
            print(f"    registry: {s}")

        # Explicit --map wins; otherwise pair in order when the counts agree.
        mapped = [(v, explicit[v["key"]]) for v in recs if v.get("key") in explicit]
        rest_v = [v for v in recs if v.get("key") not in explicit]
        rest_s = [s for s in sessions if s not in {m[1] for m in mapped}]
        if mapped:
            pairs += mapped
        if len(rest_v) == len(rest_s):
            pairs += list(zip(rest_v, rest_s))
            if rest_v:
                print(f"    -> paired {len(rest_v)} in order")
        elif rest_v or rest_s:
            problems.append(
                f"talk {tid}: {len(recs)} vault recording(s) vs {len(sessions)} "
                f"registry session(s) — pair them with --map, or fix the registry")
            print(f"    ! {len(rest_v)} unpaired recording(s), "
                  f"{len(rest_s)} unpaired session(s)")

    # Write chapters for every confidently paired session.
    wrote, skipped = 0, 0
    for v, session in pairs:
        doc = chapters.get(v.get("key"))
        if not doc or not doc.get("chapters"):
            print(f"  · {session}: no chapters in the export for {v.get('key')!r}")
            skipped += 1
            continue
        d = T.session_dir(session)
        if not d.exists():
            print(f"  ! {session}: no such session dir at {d}")
            skipped += 1
            continue
        payload = {"total": doc.get("total"), "chapters": doc["chapters"],
                   "imported_from": {"vault_key": v.get("key"), "title": v.get("title")}}
        out = d / "analysis" / "chapters.json"
        if args.write:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, indent=2))
        wrote += 1
        verb = "wrote" if args.write else "would write"
        print(f"  · {verb} {len(doc['chapters'])} chapters -> {session}/analysis/chapters.json")

    print(f"\n{'✓' if args.write else '·'} {wrote} session(s) "
          f"{'updated' if args.write else 'ready (dry run)'}"
          + (f", {skipped} skipped" if skipped else ""))
    if problems:
        print("\nUnresolved:")
        for p in problems:
            print(f"  - {p}")
    if not args.write and wrote:
        print("\nRe-run with --write to apply, then:  bash scripts/widgets_all.sh")
    if problems:
        sys.exit(2)


if __name__ == "__main__":
    main()
