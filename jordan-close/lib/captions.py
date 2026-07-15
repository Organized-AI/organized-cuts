"""Build burned-in caption files (ASS) from the word-level TwelveLabs transcript.

The transcript is word-level and each word is duplicated (two index models), so
we dedupe, then group words into short readable cues (<=~5 words / ~2.5s / on
sentence breaks). Times are rebased to the reel's local timeline.
"""
from __future__ import annotations
import json
import pathlib
import re

MAX_WORDS = 5
MAX_DUR = 2.6          # seconds per cue
PAUSE_GAP = 0.7        # split a cue on a spoken pause this long
MIN_CUE = 0.7          # floor on cue display time

# Known speech-to-text mishearings → canonical spelling. Whisper routinely renders
# "Claude" as "Clod"/"Claud"/etc. Matched case-insensitively on word boundaries,
# so "Clod's" → "Claude's" and "clod." → "Claude.". Extend per-project via
# add_corrections() (project.json "caption_corrections").
# NOTE: "cloud" is deliberately NOT here — it's a real word. Only enable it for a
# specific talk via add_corrections({"cloud": "Claude"}).
CORRECTIONS = {
    "clod": "Claude",
    "claud": "Claude",
    "clode": "Claude",
    "clawed": "Claude",
}
_correct_re = None


def _build_correct_re():
    global _correct_re
    keys = sorted((re.escape(k) for k in CORRECTIONS), key=len, reverse=True)
    _correct_re = re.compile(r"\b(" + "|".join(keys) + r")\b", re.IGNORECASE) if keys else None


def add_corrections(mapping: dict):
    """Merge extra {heard: canonical} fixes (e.g. from project.json) and rebuild."""
    if mapping:
        CORRECTIONS.update({k.lower(): v for k, v in mapping.items()})
        _build_correct_re()


def correct_text(text: str) -> str:
    if not _correct_re or not text:
        return text
    return _correct_re.sub(lambda m: CORRECTIONS[m.group(1).lower()], text)


_build_correct_re()


def load_words(path: pathlib.Path):
    words = []
    prev = None
    for s in json.loads(path.read_text()):
        text = correct_text(s["text"])           # fix mis-transcribed names (Clod → Claude)
        key = (round(s["start"], 2), text)
        if text and key != prev:                 # drop exact duplicates
            words.append({**s, "text": text})
            prev = key
    return words


def build_cues(words, win_start, win_end):
    """Group words overlapping [win_start, win_end] into cues (absolute time)."""
    ws = [w for w in words if w["end"] > win_start and w["start"] < win_end]
    ws.sort(key=lambda w: w["start"])
    cues, cur = [], []

    def flush():
        if not cur:
            return
        start = cur[0]["start"]
        end = min(cur[-1]["end"], start + MAX_DUR)
        end = max(end, start + MIN_CUE)
        cues.append({"start": start, "end": end,
                     "text": " ".join(w["text"] for w in cur).strip()})
        cur.clear()

    for i, w in enumerate(ws):
        if cur:
            gap = w["start"] - cur[-1]["end"]
            span = w["end"] - cur[0]["start"]
            if gap > PAUSE_GAP or span > MAX_DUR or len(cur) >= MAX_WORDS:
                flush()
        cur.append(w)
        if w["text"][-1:] in ".?!":
            flush()
    flush()

    # prevent overlaps
    for a, b in zip(cues, cues[1:]):
        if a["end"] > b["start"]:
            a["end"] = max(a["start"] + MIN_CUE, b["start"] - 0.02)
    return cues


def _ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reel, Arial, 64, &H00FFFFFF, &H00000000, &H90000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 5, 2, 2, 70, 70, {marginv}, 1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


import os

_ROOT = pathlib.Path(__file__).resolve().parent.parent
# Caption style — matches the "Jordan" reference reels: gold Playfair Display
# bold-italic, sentence case, lower third.
CAP_COLOR = (238, 209, 27, 255)          # #EED11B gold
CAP_STROKE = (0, 0, 0, 235)
CAP_STROKE_W = 5
CAP_FONTSIZE = 84
CAP_YCENTER = 1580                        # ~0.82 * 1920
PLAYFAIR = _ROOT / "assets" / "fonts" / "PlayfairDisplay-Italic-var.ttf"
FONT_FALLBACKS = [
    "/System/Library/Fonts/Supplemental/Georgia Bold Italic.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman Bold Italic.ttf",
]


def _font(size):
    from PIL import ImageFont
    if PLAYFAIR.exists():
        try:
            f = ImageFont.truetype(str(PLAYFAIR), size)
            try:
                f.set_variation_by_axes([800])   # bold weight on the variable font
            except Exception:
                pass
            return f
        except Exception:
            pass
    for p in FONT_FALLBACKS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(draw, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if not cur or draw.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_cue_png(text, out_path, W=1080, H=1920, fontsize=CAP_FONTSIZE, y_center=CAP_YCENTER):
    """Transparent full-frame PNG with a centered caption in the Jordan style
    (gold Playfair bold-italic, sentence case, dark outline for legibility)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font(fontsize)
    lines = _wrap(d, text, font, W - 140)          # keep spoken case
    lh = int(fontsize * 1.24)
    y = y_center - (lh * len(lines)) / 2
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) / 2, y), ln, font=font, fill=CAP_COLOR,
               stroke_width=CAP_STROKE_W, stroke_fill=CAP_STROKE)
        y += lh
    img.save(out_path)
    return out_path


def build_caption_pngs(cues, offset, dur, outdir: pathlib.Path, prefix, **style):
    """Render one PNG per cue; return [(path, start_rel, end_rel)] within [0,dur]."""
    out = []
    for i, c in enumerate(cues):
        s = max(0.0, c["start"] - offset)
        e = min(c["end"] - offset, dur)
        if e <= 0 or s >= dur or not c["text"].strip():
            continue
        p = outdir / f"{prefix}_{i:03d}.png"
        render_cue_png(c["text"], p, **style)
        out.append((str(p), round(s, 2), round(e, 2)))
    return out


def write_ass(cues, offset, dur, out_path: pathlib.Path, marginv=330):
    """offset = reel start in source time; only cues within [0,dur] are kept."""
    lines = [ASS_HEADER.format(marginv=marginv)]
    for c in cues:
        s = c["start"] - offset
        e = min(c["end"] - offset, dur)
        if e <= 0 or s >= dur:
            continue
        s = max(0.0, s)
        text = c["text"].replace("\n", " ").replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{_ts(s)},{_ts(e)},Reel,,0,0,0,,{text}")
    out_path.write_text("\n".join(lines))
    return out_path
