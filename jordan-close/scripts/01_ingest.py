#!/usr/bin/env python3
"""01 — Create the index and upload the 720p proxy for analysis.

Idempotent: reuses an existing index of the same name and skips upload if a
ready video is already recorded in state.json.

    ./.venv/bin/python scripts/01_ingest.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C


def find_index(client):
    for idx in client.indexes.list():
        d = C.dump(idx)
        if d.get("index_name") == C.INDEX_NAME:
            return d.get("id") or d.get("_id")
    return None


def main():
    if not C.PROXY.exists():
        C.die(f"Proxy not found: {C.PROXY}")
    client = C.client()

    # 1. Index (reuse if present) ------------------------------------------
    index_id = find_index(client)
    if index_id:
        print(f"• Reusing existing index '{C.INDEX_NAME}' -> {index_id}")
    else:
        print(f"• Creating index '{C.INDEX_NAME}' ({C.GENERATIVE_MODEL} + {C.EMBED_MODEL}, addons={C.INDEX_ADDONS})")
        res = C.dump(client.indexes.create(
            index_name=C.INDEX_NAME,
            models=C.INDEX_MODELS,
            addons=C.INDEX_ADDONS,
        ))
        index_id = res.get("id") or res.get("_id")
        print(f"  -> {index_id}")
    C.save_state(index_id=index_id)

    # Skip upload if we already have a ready video for this index ------------
    st = C.load_state()
    if st.get("video_id") and st.get("status") == "ready" and st.get("index_id") == index_id:
        print(f"• Video already ready ({st['video_id']}); skipping upload.")
        return

    # 2. Upload proxy (local file, no URL) ---------------------------------
    print(f"• Uploading proxy {C.PROXY.name} ({C.PROXY.stat().st_size/1e6:.0f} MB)…")
    with open(C.PROXY, "rb") as fh:
        task = C.dump(client.tasks.create(
            index_id=index_id,
            video_file=(C.PROXY.name, fh, "video/mp4"),
        ))
    task_id = task.get("id") or task.get("_id")
    print(f"  task {task_id} — indexing (poll every 5s)…")
    C.save_state(task_id=task_id, video_id=task.get("video_id"))

    def on_poll(t):
        d = C.dump(t)
        print(f"    status: {d.get('status')}")

    done = C.dump(client.tasks.wait_for_done(task_id, sleep_interval=5.0, callback=on_poll))
    status = done.get("status")
    video_id = done.get("video_id")
    C.save_state(task_id=task_id, video_id=video_id, status=status)
    if status != "ready":
        C.die(f"Indexing finished with status={status} (expected 'ready').")
    print(f"✓ Ready. video_id={video_id}")


if __name__ == "__main__":
    main()
