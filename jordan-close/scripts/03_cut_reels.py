#!/usr/bin/env python3
"""03 — Cut one captioned 9:16 reel per clip from the ProRes masters.

  • talk clips: ISO1 only, subject-aware crop (follows the frame-right speaker).
  • demo clips: short presenter lead-in, then the ISO2 screen feed with the
    presenter (ISO1 — the "main" camera) kept in view as a picture-in-picture.
Audio is ISO1 throughout (masters are frame-synced). Word-grouped transcript
captions are burned into every reel.

Outputs reels/reel_<id>.mp4 plus compare stills, and writes reels/manifest.json.

    ./.venv/bin/python scripts/03_cut_reels.py [--only 03,05]
"""
import json
import os
import subprocess
import sys
import tempfile
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from lib import common as C
from lib import captions as CAP

TMP = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_", dir="/tmp"))
WORDS = None  # loaded in main()

# Per-speaker caption colour (Playfair font stays constant across speakers).
CAP.CAP_COLOR = tuple(list(C.CAPTION_COLOR) + [255])

PH = round(C.PIP_W * C.MASTER_H / C.CROP_W)          # presenter PiP height (keeps aspect)
BW, BH = C.PIP_W + 2 * C.PIP_BORDER, PH + 2 * C.PIP_BORDER
OX, OY = 1080 - BW - C.PIP_MARGIN, C.PIP_MARGIN       # top-right inset

# 9:16 "fit on blurred backdrop" for the screen feed (standalone, unique labels).
SCREEN_FIT = (
    "split=2[sbg][sfg];"
    "[sbg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:2[sbgb];"
    "[sfg]scale=1080:-2[sfgs];"
    "[sbgb][sfgs]overlay=(W-w)/2:(H-h)/2,setsar=1"
)


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        tail = "\n".join(p.stderr.strip().splitlines()[-10:])
        raise RuntimeError(f"ffmpeg failed ({p.returncode}):\n{tail}")


def make_caption_pngs(cid, start, dur):
    """Render transcript captions as transparent PNGs for a reel that starts at
    `start` (source time) and lasts `dur`. Returns [(png, s_rel, e_rel)]."""
    if not C.CAPTIONS or WORDS is None:
        return []
    cues = CAP.build_cues(WORDS, start, start + dur)
    return CAP.build_caption_pngs(cues, start, dur, TMP, f"cap_{cid}")


def caption_track(cid, pngs, dur):
    """Assemble cues into ONE transparent caption clip via the concat demuxer
    (blank PNG fills the gaps). Returns the concat list path, or None."""
    if not pngs:
        return None
    from PIL import Image
    blank = TMP / "blank.png"
    if not blank.exists():
        Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)).save(blank)
    segs, t = [], 0.0
    for p, s, e in pngs:
        if s > t:
            segs.append((blank, s - t))
        segs.append((pathlib.Path(p), max(0.05, e - s)))
        t = e
    if t < dur:
        segs.append((blank, dur - t))
    lst = TMP / f"caplist_{cid}.txt"
    with open(lst, "w") as f:
        for p, d in segs:
            f.write(f"file '{p}'\nduration {d:.3f}\n")
        f.write(f"file '{segs[-1][0]}'\n")  # concat demuxer needs the last file repeated
    return lst


def subject_cx(master, start, end, n=5):
    import cv2
    fr = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    pr = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    ts = [start] if end <= start else [start + (end - start) * i / (n - 1) for i in range(n)]
    cxs = []
    for i, t in enumerate(ts):
        fp = TMP / f"cx_{i}.jpg"
        run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", master, "-frames:v", "1", str(fp)])
        img = cv2.imread(str(fp))
        if img is None:
            continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        W = img.shape[1]
        faces = list(fr.detectMultiScale(g, 1.1, 5, minSize=(80, 80))) + \
                list(pr.detectMultiScale(g, 1.1, 5, minSize=(80, 80)))
        if len(faces):
            x, _, w, _ = max(faces, key=lambda b: b[2] * b[3])
            cxs.append((x + w / 2) / W)
    if not cxs:
        return C.DEFAULT_CX
    cxs.sort()
    return cxs[len(cxs) // 2]


def crop_x(cx):
    x0 = int(round(cx * C.MASTER_W - C.CROP_W / 2))
    x0 = max(0, min(C.MASTER_W - C.CROP_W, x0))
    return x0 - (x0 % 2)


ENC = ["-c:v", "h264_videotoolbox", "-b:v", "8000k", "-c:a", "aac", "-b:a", "160k",
       "-movflags", "+faststart"]


def cap_input(lst):
    return ["-f", "concat", "-safe", "0", "-i", str(lst)] if lst else []


def talk_reel(start, dur, x0, lst, out):
    cin = cap_input(lst)
    if cin:
        fc = (f"[0:v]crop={C.CROP_W}:{C.MASTER_H}:{x0}:0,scale=1080:1920,setsar=1[bg];"
              f"[bg][1:v]overlay=0:0:shortest=1[v]")
        final = "v"
    else:
        fc = f"[0:v]crop={C.CROP_W}:{C.MASTER_H}:{x0}:0,scale=1080:1920,setsar=1[v]"
        final = "v"
    run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", C.MASTERS["ISO1"]]
        + cin + ["-filter_complex", fc, "-map", f"[{final}]", "-map", "0:a"] + ENC + [str(out)])


def demo_reel(start, dur, x0, lead, lst, out):
    CW, H = C.CROP_W, C.MASTER_H
    core = (
        f"[0:v]trim=0:{lead:.3f},setpts=PTS-STARTPTS,crop={CW}:{H}:{x0}:0,scale=1080:1920,setsar=1[lead];"
        f"[1:v]trim={lead:.3f}:{dur:.3f},setpts=PTS-STARTPTS,{SCREEN_FIT}[scr];"
        f"[0:v]trim={lead:.3f}:{dur:.3f},setpts=PTS-STARTPTS,crop={CW}:{H}:{x0}:0,"
        f"scale={C.PIP_W}:{PH},setsar=1,pad={BW}:{BH}:{C.PIP_BORDER}:{C.PIP_BORDER}:white[pip];"
        f"[scr][pip]overlay={OX}:{OY}[body];"
        f"[lead][body]concat=n=2:v=1:a=0,scale=1080:1920,setsar=1[comp]"
    )
    cin = cap_input(lst)
    if cin:
        fc = core + ";[comp][2:v]overlay=0:0:shortest=1[v]"
    else:
        fc = core.replace("[comp]", "[v]")
    run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", C.MASTERS["ISO1"],
         "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", C.MASTERS["ISO2"]]
        + cin + ["-filter_complex", fc, "-map", "[v]", "-map", "0:a"] + ENC + [str(out)])


def still_person(t, x0, out):
    run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", C.MASTERS["ISO1"],
         "-vf", f"crop={C.CROP_W}:{C.MASTER_H}:{x0}:0,scale=1080:1920", "-frames:v", "1", "-q:v", "3", str(out)])


def still_screen(t, out):
    run(["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", C.MASTERS["ISO2"],
         "-filter_complex", f"[0:v]{SCREEN_FIT}[v]", "-map", "[v]", "-frames:v", "1", "-q:v", "3", str(out)])


def main():
    global WORDS
    argv = sys.argv[1:]
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else None

    for angle, path in C.MASTERS.items():
        if not os.path.exists(path):
            C.die(f"Master not found ({angle}): {path}")
    tpath = C.ANALYSIS / "transcript.json"
    if C.CAPTIONS and tpath.exists():
        WORDS = CAP.load_words(tpath)
        print(f"• captions: {len(WORDS)} words loaded")
    elif C.CAPTIONS:
        print("• captions: transcript.json missing — run scripts/fetch_transcript.py; cutting without captions")

    data = json.loads(C.CLIPS_PATH.read_text())
    clips = [c for c in data["clips"] if (only is None or c["id"] in only)]
    C.COMPARE.mkdir(parents=True, exist_ok=True)

    manifest = []
    for c in clips:
        s0 = max(0.0, c["start"] - C.PAD)
        dur = (c["end"] + C.PAD) - s0
        mid = (c["start"] + c["end"]) / 2.0
        cx = subject_cx(C.MASTERS["ISO1"], c["start"], c["end"])
        x0 = crop_x(cx)
        pngs = make_caption_pngs(c["id"], s0, dur)
        lst = caption_track(c["id"], pngs, dur)
        reel = C.REEL_OUT / f"reel_{c['id']}.mp4"
        kind = c.get("kind", "talk")
        if kind == "demo" and not C.ISO2_PRESENT:
            kind = "talk"

        if kind == "demo":
            lead = min(C.DEMO_LEAD_S, max(1.0, dur * 0.35))
            demo_reel(s0, dur, x0, lead, lst, reel)
            still_screen(mid, C.COMPARE / f"{c['id']}_screen.jpg")
            treatment = f"ISO1 lead {lead:.1f}s → ISO2 screen + presenter PiP"
            sources = ["ISO1", "ISO2"]
        else:
            talk_reel(s0, dur, x0, lst, reel)
            lead = None
            treatment = "ISO1 talking-head"
            sources = ["ISO1"]
        still_person(mid, x0, C.COMPARE / f"{c['id']}_person.jpg")

        manifest.append({
            "id": c["id"], "kind": kind, "treatment": treatment, "sources": sources,
            "captions": len(pngs), "hook": c["hook"], "caption": c["caption"],
            "start": c["start"], "end": c["end"], "duration": c["duration"],
            "crop_cx": round(cx, 3), "crop_x0": x0, "demo_lead_s": (round(lead, 2) if lead else None),
            "reel": f"reels/reel_{c['id']}.mp4",
            "still_person": f"reels/compare/{c['id']}_person.jpg",
            "still_screen": (f"reels/compare/{c['id']}_screen.jpg" if kind == "demo" else None),
        })
        print(f"[{c['id']}] {kind:<4} cx={cx:.2f} x0={x0:<4} caps={len(pngs):<2} {treatment}  -> {reel.name} ({reel.stat().st_size/1e6:.1f} MB)")

    # With --only, merge into the existing manifest instead of clobbering it.
    if only and C.MANIFEST_PATH.exists():
        existing = json.loads(C.MANIFEST_PATH.read_text()).get("clips", [])
        by_id = {m["id"]: m for m in existing}
        for m in manifest:
            by_id[m["id"]] = m
        merged = [by_id[k] for k in sorted(by_id)]
    else:
        merged = manifest
    C.MANIFEST_PATH.write_text(json.dumps({"video_id": data.get("video_id"), "clips": merged}, indent=2))
    print(f"\n✓ Cut {len(clips)} reels -> {C.REEL_OUT}  |  manifest -> {C.MANIFEST_PATH}")


if __name__ == "__main__":
    main()
