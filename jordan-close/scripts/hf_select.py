#!/usr/bin/env python3
"""Pick 5 clips per speaker for the animated series (demo-tagged first, then
highest-score, chronological). Writes animated/selection.json."""
import json
import pathlib

OC = pathlib.Path("/Users/supabowl/organized-cuts")
SPEAKERS = {
    "Jordan": ["jordan-close"],
    "Rohit": ["session-3-rohit", "session-3a-rohit"],
    "CT": ["session-2-ct"],
    "Michael": ["session-4-michael", "session-4a-michael", "session-5-michael", "session-5a-michael"],
    "Esteban": ["session-1-esteban"],
    "Shep": ["session-6a-shep"],   # session-6-shep has no ISO2 -> can't animate
}


def key(session, cid):
    s = session.replace("session-", "s").replace("jordan-close", "jordan")
    return f"{s}_{cid}"


def main():
    sel = []
    for spk, sessions in SPEAKERS.items():
        pool = []
        for sess in sessions:
            m = OC / sess / "reels" / "manifest.json"
            if not m.exists():
                print(f"  ! {spk}: {sess} manifest missing")
                continue
            for c in json.load(open(m))["clips"]:
                if "ISO2" not in c.get("sources", []) and c["kind"] != "demo":
                    # still animatable only if ISO2 exists for the session; demo implies it
                    pass
                pool.append({"session": sess, "id": c["id"], "kind": c["kind"],
                             "score": c.get("score", 0), "start": c["start"], "hook": c.get("hook", "")})
        # demo first, then by score; take 5; then chronological
        pool.sort(key=lambda x: (0 if x["kind"] == "demo" else 1, -x["score"]))
        pick = pool[:5]
        pick.sort(key=lambda x: (x["session"], x["start"]))
        for p in pick:
            p["speaker"] = spk
            p["key"] = key(p["session"], p["id"])
            sel.append(p)
        print(f"  {spk:9} -> {len(pick)} clips: " + ", ".join(f"{p['session'].split('-')[-1]}#{p['id']}" for p in pick))
    (OC / "animated" / "selection.json").write_text(json.dumps(sel, indent=2))
    print(f"\n✓ {len(sel)} clips -> animated/selection.json")


if __name__ == "__main__":
    main()
