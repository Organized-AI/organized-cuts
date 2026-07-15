"""Shared config + helpers for the Organized Cuts reel pipeline.

Multi-project: a session's data dir is chosen by the OC_PROJECT_DIR env var
(default: the code dir = Jordan Close). Per-session settings live in
<project>/project.json (masters, index name, proxy, caption color, upload
folder). State (index_id, video_id, task_id) is persisted to
<project>/analysis/state.json so each numbered script is re-runnable.
"""
from __future__ import annotations
import json
import os
import pathlib
import sys

CODE_ROOT = pathlib.Path(__file__).resolve().parent.parent   # where scripts/lib/.env live
PROJECT_DIR = pathlib.Path(os.environ.get("OC_PROJECT_DIR", str(CODE_ROOT))).resolve()
ROOT = PROJECT_DIR                                            # data root for this session


def _cfg() -> dict:
    p = PROJECT_DIR / "project.json"
    return json.loads(p.read_text()) if p.exists() else {}


CFG = _cfg()

# --- Inputs -----------------------------------------------------------------
# Proxy is ONLY for TwelveLabs analysis. Final reels are cut from the masters.
_DEFAULT_MASTERS = {
    "ISO1": "/Volumes/T7/Vol 2 Workshop/Jordan Close/JORDAN_S001_S001_T011_ISO1.MOV",
    "ISO2": "/Volumes/T7/Vol 2 Workshop/Jordan Close/JORDAN_S001_S001_T011_ISO2.MOV",
}
MASTERS = {k: v for k, v in CFG.get("masters", _DEFAULT_MASTERS).items() if v}
ISO2_PRESENT = bool(MASTERS.get("ISO2"))

_proxy = CFG.get("proxy", "proxy/jordan_close_ISO1_720p.mp4")
PROXY = pathlib.Path(_proxy) if os.path.isabs(_proxy) else PROJECT_DIR / _proxy

SPEAKER = CFG.get("speaker", "Jordan")
UPLOAD_FOLDER = CFG.get("upload_folder", "Vol 2 Workshop/Jordan Close — Reels")
CAPTION_COLOR = tuple(CFG.get("caption_color", [238, 209, 27]))   # RGB; per-speaker

# --- Variant (short vs long reels) ------------------------------------------
# OC_VARIANT lets a session produce a SECOND, longer set of reels alongside the
# default short ones without clobbering them. "" = default 20-45s short reels;
# "long" = 45-90s (0:45-1:30). Clip outputs are suffixed (clips_long.json,
# reels_long/) while the index + transcript (state.json, transcript.json) are
# shared, so the long run reuses the existing ingest and Whisper pass.
VARIANT = os.environ.get("OC_VARIANT", "").strip().lower()
_VSUF = f"_{VARIANT}" if VARIANT else ""
_VARIANT_CLIP = {
    "":     (20.0, 45.0, (6, 10)),   # default short reels
    "long": (45.0, 90.0, (4, 7)),    # 0:45-1:30 long-form reels
}
_vmin, _vmax, _vcount = _VARIANT_CLIP.get(VARIANT, _VARIANT_CLIP[""])

# --- Outputs ----------------------------------------------------------------
ANALYSIS = ROOT / "analysis"                    # shared across variants
REELS = ROOT / f"reels{_VSUF}"                  # reels/ or reels_long/
COMPARE = REELS / "compare"
STATE_PATH = ANALYSIS / "state.json"            # shared (index/video ids)
CLIPS_PATH = ANALYSIS / f"clips{_VSUF}.json"    # clips.json or clips_long.json
MANIFEST_PATH = REELS / "manifest.json"

# --- TwelveLabs config ------------------------------------------------------
INDEX_NAME = CFG.get("index_name", "jordan-close-workshop")
# Generative (Pegasus) + embedding/search (Marengo). model_options gate which
# modalities are indexed; visual+audio covers a talk with a speaker + slides.
GENERATIVE_MODEL = "pegasus1.2"
EMBED_MODEL = "marengo3.0"
INDEX_MODELS = [
    {"model_name": GENERATIVE_MODEL, "model_options": ["visual", "audio"]},
    {"model_name": EMBED_MODEL, "model_options": ["visual", "audio"]},
]
INDEX_ADDONS = ["thumbnail"]

# Clip targeting (variant-driven; override the length with OC_CLIP_MIN_S / _MAX_S)
CLIP_MIN_S = float(os.environ.get("OC_CLIP_MIN_S", _vmin))
CLIP_MAX_S = float(os.environ.get("OC_CLIP_MAX_S", _vmax))
CLIP_TARGET_COUNT = _vcount

# --- Reframing / editing ----------------------------------------------------
# Defaults assume a 1920x1080 master (a 9:16 crop of the 1080-tall frame is
# 607.5px wide → even 608). These are OVERRIDDEN at cut time by probing the
# actual ISO1 master (03_cut_reels.py), so 4K/other resolutions crop correctly.
# The subject crop is centred on a per-clip, face-tracked x, falling back to
# DEFAULT_CX (per-project via project.json "default_cx"; 0=left, 1=right).
MASTER_W, MASTER_H = 1920, 1080
CROP_W = 608
DEFAULT_CX = float(CFG.get("default_cx", 0.58))   # subject centre fallback
PAD = 0.3                   # lead/tail seconds around each clip
DEMO_LEAD_S = 2.0           # presenter full-frame hold before the PiP layout
REEL_OUT = REELS            # single reel per clip -> reels/reel_<id>.mp4

# Demo clips keep the presenter (ISO1, the "main" camera) in view as a
# picture-in-picture over the ISO2 screen feed.
PIP_W = 348                 # presenter inset width (px); height derived from crop aspect
PIP_MARGIN = 40
PIP_BORDER = 4
CAPTIONS = True             # burn word-grouped transcript captions into every reel

# A clip is treated as a "demo" (cut to the ISO2 screen feed) when the analysis
# says so or the transcript references the screen.
DEMO_QUERY = "clear demo or reveal moment"
DEMO_KEYWORDS = [
    "show you", "showing", "let me show", "on the screen", "on screen", "you can see",
    "if you look", "over here", "this page", "this dashboard", "dashboard", "click",
    "leaderboard", "scan", "qr code", "check-in", "live", "demo", "reveal", "pull up",
    "take a look", "right here", "up here", "as you can see",
]

SEARCH_QUERIES = [
    "strongest hook opener",
    "quotable one-liner",
    "actionable takeaway builders can use",
    "emotional or funny peak",
    "clear demo or reveal moment",
]


def die(msg: str, code: int = 1):
    print(f"\n\033[31mERROR:\033[0m {msg}", file=sys.stderr)
    sys.exit(code)


def get_api_key() -> str:
    """Resolve TWELVELABS_API_KEY from env or a local (gitignored) .env file."""
    key = os.environ.get("TWELVELABS_API_KEY")
    if key:
        return key.strip()
    for envf in (CODE_ROOT / ".env", PROJECT_DIR / ".env"):
        if envf.exists():
            for line in envf.read_text().splitlines():
                line = line.strip()
                if line.startswith("TWELVELABS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    die(
        "TWELVELABS_API_KEY not found.\n"
        "  Provide it via one of:\n"
        "    - export TWELVELABS_API_KEY=... in your shell, or\n"
        "    - a line  TWELVELABS_API_KEY=...  in jordan-close/.env, or\n"
        "    - scripts/00_fetch_key.sh  (Infisical, if the CLI is configured)."
    )


def client():
    from twelvelabs import TwelveLabs

    return TwelveLabs(api_key=get_api_key())


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def save_state(**kw) -> dict:
    s = load_state()
    s.update({k: v for k, v in kw.items() if v is not None})
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(s, indent=2))
    return s


def require_state(*keys) -> dict:
    s = load_state()
    missing = [k for k in keys if not s.get(k)]
    if missing:
        die(f"Missing pipeline state {missing} in {STATE_PATH}. Run the earlier step first.")
    return s


def dump(obj):
    """Best-effort convert an SDK pydantic object / list to plain dict/list."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, list):
        return [dump(x) for x in obj]
    return obj
