#!/usr/bin/env python3
"""10 — Build a previewable copy of the continuous long-cut page.

talkmap/vault/continuous.html ships with no chapter data: on the vault it
fetches /api/videos and /api/chapters itself. This injects the merged bundle
into that same page so the subject index can be explored without a member
session — the map is live, the video is not.

    ./.venv/bin/python scripts/10_continuous.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import talkmap as T

TEMPLATE = T.REPO_ROOT / "talkmap" / "vault" / "continuous.html"
OUT = T.BUILD_DIR / "continuous-preview.html"


def build_vault_preview(talks):
    """Also emit a previewable copy of the whole vault page.

    The shipped vault.html talks to the real API; rather than teach it a preview
    mode it will never use in production, this prepends a build-time shim that
    answers /api/* from the bundle. The page then runs exactly as deployed —
    same gate, same switch, same long cut — only the video is missing, since
    /media needs the member session.
    """
    vault = T.REPO_ROOT / "talkmap" / "vault" / "vault.html"
    if not vault.exists():
        return
    data = {
        "videos": [{"key": t["key"], "title": t["title"], "size": 0} for t in talks],
        "chapters": {t["key"]: {"total": t["total"], "chapters": t["chapters"]}
                     for t in talks},
    }
    shim = ("<script>\n(function(){\n  var D=" +
            json.dumps(data, separators=(",", ":")) + ";\n"
            "  function jr(o){return{ok:true,status:200,json:function(){return Promise.resolve(o)}}}\n"
            "  var no={ok:false,status:404,json:function(){return Promise.resolve({})}};\n"
            "  window.fetch=function(u){u=String(u);\n"
            "    if(u.indexOf('/api/videos')===0) return Promise.resolve(jr({videos:D.videos}));\n"
            "    if(u.indexOf('/api/chapters')===0){var k=decodeURIComponent(u.split('video=')[1]||'');\n"
            "      return Promise.resolve(D.chapters[k]?jr(D.chapters[k]):no)}\n"
            "    if(u.indexOf('/api/me')===0) return Promise.resolve(jr({email:'preview'}));\n"
            "    if(u.indexOf('/api/search')===0) return Promise.resolve(jr({results:[]}));\n"
            "    return Promise.resolve(no)};\n"
            "})();\n</script>\n")
    html = vault.read_text()
    marker = "<script>\nconst $=id=>document.getElementById(id);"
    if marker not in html:
        marker = "<script>\nconst $=id=>document.getElementById(id);".replace("\n", "\r\n")
    if marker in html:
        html = html.replace(marker, shim + marker, 1)
    else:                      # fall back: shim just before the closing body
        html = html.replace("</body>", shim + "</body>", 1)
    banner = ('<div style="background:#1a1814;border:1px solid #8b7a12;border-radius:10px;'
              'padding:13px 17px;margin:0 0 22px;font-family:JetBrains Mono,monospace;'
              'font-size:11.5px;color:#a09888;letter-spacing:.04em">PREVIEW BUILD — map and '
              'subject index are live on the real chapters. Video needs the vault session, so '
              'playback is inert here. Use the <b style="color:#f5d623">SESSIONS / LONG CUT</b> '
              'switch to compare the two views.</div>')
    html = html.replace('<div class="vhead">', banner + '<div class="vhead">', 1)
    out = T.BUILD_DIR / "vault-preview.html"
    out.write_text(html)
    print(f"✓ {out}  ({out.stat().st_size/1024:.0f} KB)")


def main():
    bundle_path = T.BUILD_DIR / "talkmap.json"
    bundle = T.read_json(bundle_path)
    if not bundle:
        sys.exit(f"No bundle at {bundle_path}. Run 08_talkmap.py first.")

    talks = []
    for t in bundle["talks"]:
        if not t["chapters"]:
            continue
        meta = T.load_talk_chapters(t["id"]) or {}
        key = (meta.get("imported_from") or {}).get("vault_key") or f"{t['id']} {t['speaker']}.mp4"
        talks.append({
            "id": t["id"], "key": key, "speaker": t["speaker"],
            "title": f"{t['speaker']} — {t['title']}",
            "total": t["total"],
            "chapters": [{"start": c["start"], "end": c["end"], "title": c["title"],
                          "summary": c["summary"], "category": c["category"],
                          "color": c["color"]} for c in t["chapters"]],
        })
    if not talks:
        sys.exit("No talks carry chapters yet — run import_talkmap.py --write.")

    html = TEMPLATE.read_text().replace(
        "/*__DATA__*/null", json.dumps({"talks": talks}, separators=(",", ":")), 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    build_vault_preview(talks)

    total = sum(t["total"] for t in talks)
    print(f"• {len(talks)} talks, {sum(len(t['chapters']) for t in talks)} chapters, "
          f"{total/3600:.2f}h continuous")
    print(f"✓ {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
