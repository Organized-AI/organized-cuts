# Organized Cuts — Agent Corpus

Turns the speaker corpus into components an AI agent can consume, and serves
them over MCP. An agent mounted on this server can answer questions about the
entire corpus with **exact details** (quotes, timecodes, clip copy) and offer
**precise clips**, backed by the same TwelveLabs indexes the reel pipeline
already built.

```
pipeline outputs                 agent/build_corpus.py          agent/server.py (MCP)
  project.json                ┐                                   list_sessions
  analysis/state.json         │                                   get_session
  analysis/clips.json         ├──►  agent/corpus/<name>.json ──►  search_transcripts   (offline)
  analysis/transcript.json    │     agent/corpus/corpus.json      get_clip
  reels/manifest.json         │                                   find_moments   (Marengo search)
  site widgets / widgets.json ┘                                   ask_session    (Pegasus grounded Q&A)
```

## Quick start

```bash
pip install -r agent/requirements.txt   # mcp (+ twelvelabs for semantic tools)
python3 agent/build_corpus.py           # package sessions -> agent/corpus/
python3 agent/server.py                 # serve over stdio (agents mount this)
```

Re-run `build_corpus.py` after any pipeline run — it's offline, deterministic,
and safe to re-run anytime. Sessions whose analysis lives on another machine
(see MIGRATION.md) get skeleton components until built there.

## Importing the full talks from the recordings vault

The recordings.organizedai.vip worker already holds TwelveLabs analysis for
the **complete talks** (not just the cut reels) in its KV namespace:
`tl:manifest` (per-talk parts with index/video ids + time offsets),
`tx:<video_id>` transcripts, and `chapters:<video_id>`. Pull them into the
corpus with:

```bash
export CLOUDFLARE_API_TOKEN=...     # needs KV Storage: Read
export CLOUDFLARE_ACCOUNT_ID=...
python3 agent/import_vault.py       # -> agent/corpus/vault-<talk>.json per talk
```

Vault talks carry `twelvelabs_parts` (a talk can span several indexed videos
with offsets); `find_moments` searches every part and returns timecodes on the
full-talk clock — the same clock as the vault player — and `ask_session` asks
part by part, labeling each answer with its timestamp offset.

Run `python3 agent/test_agent.py` to verify the stack offline (no API keys
needed).

## Handing it to an agent

**Claude Code** — already wired: `.mcp.json` at the repo root registers the
server, so any Claude Code session in this repo can use the tools directly.
Elsewhere: `claude mcp add organized-cuts-corpus -- python3 /path/to/organized-cuts/agent/server.py`

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "organized-cuts-corpus": {
      "command": "python3",
      "args": ["/Users/jordan/organized-cuts/agent/server.py"]
    }
  }
}
```

**Any other MCP client** — stdio transport, command `python3 agent/server.py`.

## Tools

| tool | needs | what it gives the agent |
|------|-------|------------------------|
| `list_sessions` | corpus | every session + speaker + what data it has |
| `get_session(name)` | corpus | clips (exact start/end s, hook, caption, per-clip transcript, reel file), full segmented transcript, widget specs, TwelveLabs ids |
| `search_transcripts(query, session?, limit?)` | corpus | where something was said — segments ranked by query-word coverage, each with exact timecodes |
| `get_clip(session, clip_id)` | corpus | one clip's timecodes (`tc_in`/`tc_out`), copy, and reel path |
| `find_moments(query, session?, limit?)` | `TWELVELABS_API_KEY` | Marengo semantic search over the existing indexes — natural-language queries → ranked moments with exact seconds |
| `ask_session(question, session)` | `TWELVELABS_API_KEY` | Pegasus answer grounded in the indexed video (visuals + audio), with timestamped citations |

The key resolves from the environment or `jordan-close/.env` (same as the
pipeline; fetch it with `jordan-close/scripts/00_fetch_key.sh`). Without it the
offline tools still work and the semantic tools return a clear pointer to the
offline alternatives.

## Component format (`agent/corpus/<name>.json`)

```jsonc
{
  "name": "session-4-michael",
  "title": "…", "speaker": "Michael", "media_url": null,
  "twelvelabs": { "index_name": "…", "index_id": "…", "video_id": "…" },
  "masters": { "ISO1": "/Volumes/T7/…", "ISO2": "…" },
  "clips": [ { "id": "01", "start": 462.0, "end": 497.0, "hook": "…",
               "caption": "…", "kind": "talk", "transcript": "…",
               "reel": "reels/reel_01.mp4" } ],
  "transcript": [ { "start": 460.0, "end": 468.2, "text": "…" } ],
  "widgets": [ /* site widget specs — see site/README.md */ ],
  "assets": { "reels_dir": "session-4-michael/reels", "proxy": "…" }
}
```

All timecodes are seconds from the shared start of the session's frame-synced
masters — the same clock the reels were cut on, so an agent's answer maps
1:1 onto real video.
