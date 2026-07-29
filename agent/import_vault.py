#!/usr/bin/env python3
"""Import the recordings vault's TwelveLabs data into the agent corpus.

The recordings.organizedai.vip worker keeps the *full-talk* analysis in its
VAULT KV namespace:

    tl:manifest              {"<video key>": {"total": s, "parts": [
                                 {"label","offset","index_id","video_id"}]}}
    tx:<video_id>            [[start, end, "text"], ...]      (per part)
    chapters:<video_id>      [{"start","end","title","summary"}, ...]

This script pulls those keys over the Cloudflare API and emits one corpus
component per talk (agent/corpus/vault-<slug>.json) with part offsets applied,
so the MCP server can search/answer over the complete talks — not just the
cut reels — with timecodes that match the vault player exactly.

Auth — either works:
  • wrangler OAuth (typical on a dev machine): just `python3 agent/import_vault.py`
    — keys are fetched with `npx wrangler kv key get` using your login.
  • REST: export CLOUDFLARE_API_TOKEN (KV Storage: Read) and
    CLOUDFLARE_ACCOUNT_ID, then run the same command.
  Namespace defaults to recordings-organizedai-VAULT; override with
  VAULT_KV_NAMESPACE_ID if it ever moves (`wrangler kv namespace list`).

The fetch and transform stages are separate so the transform is testable
offline: `import_vault.transform(manifest, tx_by_id, chapters_by_id)`.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "agent" / "corpus"

API = "https://api.cloudflare.com/client/v4"
# "recordings-organizedai-VAULT" namespace (from `wrangler kv namespace list`)
DEFAULT_VAULT_NS = "077b2f50bd704953a76ba71cd219c00d"


def slugify(key: str) -> str:
    s = re.sub(r"\.mp4$", "", key, flags=re.I)
    s = re.sub(r"^\d+\s*-\s*", "", s)
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return f"vault-{s or 'talk'}"


def title_of(key: str) -> str:
    return re.sub(r"^\d+\s*-\s*", "", re.sub(r"\.mp4$", "", key, flags=re.I))


def transform(manifest: dict, tx_by_id: dict, chapters_by_id: dict) -> list[dict]:
    """KV payloads -> corpus components (offsets applied, sorted, complete)."""
    components = []
    for vkey, entry in sorted(manifest.items()):
        parts = entry.get("parts", [])
        transcript, chapters = [], []
        for p in parts:
            off = float(p.get("offset", 0))
            for row in tx_by_id.get(p["video_id"], []):
                s, e, text = row[0], row[1], row[2]
                transcript.append({"start": round(off + float(s), 2),
                                   "end": round(off + float(e), 2),
                                   "text": str(text).strip()})
            for i, c in enumerate(chapters_by_id.get(p["video_id"], []), 1):
                chapters.append({
                    "id": f"{p.get('label', 'p')}-{i}",
                    "hook": c.get("title", ""),
                    "kind": "chapter",
                    "start": round(off + float(c.get("start", 0)), 2),
                    "end": round(off + float(c.get("end") or c.get("start", 0)), 2),
                    "caption": c.get("summary", ""),
                })
        transcript.sort(key=lambda t: t["start"])
        chapters.sort(key=lambda c: c["start"])
        components.append({
            "name": slugify(vkey),
            "title": title_of(vkey),
            "speaker": title_of(vkey).split("—")[0].strip(),
            "media_url": None,   # streamed via the vault (auth required)
            "vault_key": vkey,
            "duration": float(entry.get("total") or
                              (transcript[-1]["end"] if transcript else 0)),
            "twelvelabs": {"index_name": None, "index_id": None, "video_id": None},
            "twelvelabs_parts": [
                {"label": p.get("label"), "offset": float(p.get("offset", 0)),
                 "index_id": p.get("index_id"), "video_id": p.get("video_id")}
                for p in parts
            ],
            "masters": {},
            "clips": chapters,
            "transcript": transcript,
            "widgets": [],
            "assets": {"stream": f"https://recordings.organizedai.vip/media/{urllib.parse.quote(vkey)}"},
        })
    return components


# --- Cloudflare KV fetch ----------------------------------------------------

def _kv_get_rest(token: str, account: str, ns: str, key: str):
    url = (f"{API}/accounts/{account}/storage/kv/namespaces/{ns}"
           f"/values/{urllib.parse.quote(key, safe='')}")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _kv_get_wrangler(ns: str, key: str):
    """Fetch via `wrangler kv key get` (OAuth login) — no API token needed."""
    wrangler = (["wrangler"] if shutil.which("wrangler")
                else ["npx", "--yes", "wrangler"])
    r = subprocess.run(wrangler + ["kv", "key", "get", key,
                                   "--namespace-id", ns, "--remote"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        low = (r.stderr or "").lower()
        if "not found" in low or "10009" in low:
            return None
        raise RuntimeError(f"wrangler kv get {key!r} failed:\n{r.stderr.strip()}")
    return json.loads(r.stdout)


def _make_getter(ns: str):
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if token and account:
        print("• auth: Cloudflare API token")
        base = lambda key: _kv_get_rest(token, account, ns, key)  # noqa: E731
    else:
        print("• auth: wrangler login (set CLOUDFLARE_API_TOKEN + "
              "CLOUDFLARE_ACCOUNT_ID to use the REST API instead)")
        base = lambda key: _kv_get_wrangler(ns, key)              # noqa: E731

    def get(key, attempts=3):
        # Transient 401/5xx have been seen mid-run (token refresh); retry.
        for i in range(attempts):
            try:
                return base(key)
            except Exception as e:
                if i == attempts - 1:
                    raise
                print(f"  ! {key}: {e!s:.120} — retrying in {2 ** i}s")
                time.sleep(2 ** i)
    return get


def fetch_and_build():
    ns = os.environ.get("VAULT_KV_NAMESPACE_ID", DEFAULT_VAULT_NS)
    get = _make_getter(ns)

    manifest = get("tl:manifest")
    if not manifest:
        sys.exit("tl:manifest not found in the KV namespace — wrong namespace id?")

    def optional(key):
        """tx:/chapters: are enrichments — a persistent failure shouldn't
        abort the whole import. Warn and continue with what we have."""
        try:
            return get(key) or []
        except Exception as e:
            print(f"  ! skipping {key} after retries ({e!s:.120})")
            return []

    tx_by_id, chapters_by_id = {}, {}
    for entry in manifest.values():
        for p in entry.get("parts", []):
            vid = p["video_id"]
            if vid not in tx_by_id:
                tx_by_id[vid] = optional(f"tx:{vid}")
                chapters_by_id[vid] = optional(f"chapters:{vid}")
    return transform(manifest, tx_by_id, chapters_by_id)


def site_session(comp: dict) -> dict:
    """Corpus component -> the site viewer's session.json shape, so vault
    talks are browsable (chapters + transcript + timestamp jumps) in site/.
    media_url is the vault stream: playback works when the viewer is served
    under recordings.organizedai.vip (auth cookie is same-site); elsewhere
    the page still shows chapters/transcript."""
    return {
        "name": comp["name"],
        "title": comp["title"],
        "speaker": comp["speaker"],
        "media_url": comp["assets"].get("stream"),
        "duration": comp["duration"],
        "chapters": [
            {"id": c["id"], "title": c["hook"], "kind": c["kind"],
             "start": c["start"], "end": c["end"], "caption": c.get("caption", "")}
            for c in comp["clips"]
        ],
        "transcript": comp["transcript"],
        "widgets": comp["widgets"],
    }


def write(components: list[dict]):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index_path = OUT_DIR / "corpus.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else []
    site_dir = REPO / "site" / "public" / "sessions"
    site_index_path = site_dir / "index.json"
    site_index = (json.loads(site_index_path.read_text())
                  if site_index_path.exists() else [])
    for comp in components:
        (OUT_DIR / f"{comp['name']}.json").write_text(
            json.dumps(comp, indent=2, ensure_ascii=False))
        index = [e for e in index if e.get("name") != comp["name"]]
        index.append({"name": comp["name"], "title": comp["title"],
                      "speaker": comp["speaker"], "clips": len(comp["clips"]),
                      "transcript_segments": len(comp["transcript"]),
                      "widgets": 0,
                      "twelvelabs_ready": bool(comp["twelvelabs_parts"])})

        s = site_session(comp)
        (site_dir / comp["name"]).mkdir(parents=True, exist_ok=True)
        (site_dir / comp["name"] / "session.json").write_text(
            json.dumps(s, indent=2, ensure_ascii=False))
        site_index = [e for e in site_index if e.get("name") != comp["name"]]
        site_index.append({"name": comp["name"], "title": comp["title"],
                           "speaker": comp["speaker"], "duration": comp["duration"],
                           "chapters": len(s["chapters"]),
                           "widgets": len(s["widgets"])})
        print(f"  {comp['name']:<40} segs={len(comp['transcript']):>5} "
              f"chapters={len(comp['clips']):>3} parts={len(comp['twelvelabs_parts'])}")
    index.sort(key=lambda e: e["name"])
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False))
    site_index.sort(key=lambda e: e["name"])
    site_index_path.write_text(json.dumps(site_index, indent=2, ensure_ascii=False))
    print(f"✓ {len(components)} vault talks -> {OUT_DIR.relative_to(REPO)}/ "
          f"+ site/public/sessions/")


if __name__ == "__main__":
    write(fetch_and_build())
