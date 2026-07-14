#!/usr/bin/env python3
"""Transcribe the ISO1 audio with Whisper large-v3 (accurate word timestamps)
and overwrite analysis/transcript.json (list of {start,end,text} words).

Uses mlx-whisper (Apple MLX, runs large-v3 on the GPU — ~3x realtime vs ~0.2x
on CPU). Falls back to faster-whisper CPU if MLX is unavailable.

    OC_PROJECT_DIR=../session-x ./.venv/bin/python scripts/whisper_transcript.py
"""
import json
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C

AUDIO = C.ANALYSIS / "iso1_audio.wav"
OUT = C.ANALYSIS / "transcript.json"
MLX_REPO = "mlx-community/whisper-large-v3-mlx"


def _mlx(words_out):
    import mlx_whisper
    print(f"• transcribing {AUDIO.name} with mlx large-v3 (GPU)…")
    r = mlx_whisper.transcribe(str(AUDIO), path_or_hf_repo=MLX_REPO,
                               word_timestamps=True, language="en", verbose=False)
    for seg in r["segments"]:
        for w in seg.get("words", []):
            t = w["word"].strip()
            if t:
                words_out.append({"start": round(float(w["start"]), 3),
                                  "end": round(float(w["end"]), 3), "text": t})


def _faster_whisper_cpu(words_out):
    from faster_whisper import WhisperModel
    print("• MLX unavailable — falling back to faster-whisper large-v3 (CPU)…")
    model = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=8)
    segments, _ = model.transcribe(str(AUDIO), language="en", word_timestamps=True,
                                   vad_filter=True, beam_size=5)
    for seg in segments:
        for w in (seg.words or []):
            t = w.word.strip()
            if t:
                words_out.append({"start": round(w.start, 3), "end": round(w.end, 3), "text": t})


def main():
    if not AUDIO.exists():
        C.die(f"Audio not found: {AUDIO} (run prepare_media.py first).")
    words = []
    try:
        _mlx(words)
    except Exception as e:
        print(f"  ! mlx path failed ({e})")
        words = []
        _faster_whisper_cpu(words)
    words.sort(key=lambda w: w["start"])
    OUT.write_text(json.dumps(words, indent=2))
    print(f"✓ {len(words)} words -> {OUT}")


if __name__ == "__main__":
    main()
