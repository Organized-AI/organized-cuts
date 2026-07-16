#!/usr/bin/env python3
"""Generate a Hyperframes composition for one demo clip, in a chosen VARIANT.

Variants (punchy GSAP motion between the two synced ISOs):
  whip  — energetic: multiple fast whip/zoom cuts ISO1<->ISO2, PiP, split finish
  pip   — presenter-over-demo: quick move to screen with a spring PiP that holds
  split — split-screen dominant: both angles most of the clip, punch to full screen

    ./.venv/bin/python scripts/hf_build.py <asset_dir_rel> <out_html> [variant]
"""
import json
import sys
import pathlib

A = sys.argv[1]                              # asset dir rel to hf/ e.g. "assets/proto"
OUT = pathlib.Path(sys.argv[2])
VAR = sys.argv[3] if len(sys.argv) > 3 else "whip"
meta = json.loads((OUT.parent / A / "meta.json").read_text())
D = meta["duration"]
r, g, b = meta["color"]
COL = f"rgb({r},{g},{b})"


def scenes(variant, D):
    f = lambda x: round(x * D, 2)
    if variant == "pip":
        return [dict(kind="iso1", s=0, e=f(0.16), tin="none"),
                dict(kind="pip", s=f(0.16), e=f(0.72), tin="zoom"),
                dict(kind="split", s=f(0.72), e=D, tin="split")]
    if variant == "split":
        return [dict(kind="iso1", s=0, e=f(0.13), tin="none"),
                dict(kind="split", s=f(0.13), e=f(0.6), tin="split"),
                dict(kind="iso2", s=f(0.6), e=f(0.82), tin="zoom"),
                dict(kind="pip", s=f(0.82), e=D, tin="spring")]
    if variant == "punch":
        # rhythmic zoom-punch cuts (snappier, no horizontal whips)
        return [dict(kind="iso1", s=0, e=f(0.12), tin="none"),
                dict(kind="iso2", s=f(0.12), e=f(0.30), tin="punch"),
                dict(kind="iso1", s=f(0.30), e=f(0.46), tin="punch"),
                dict(kind="iso2", s=f(0.46), e=f(0.66), tin="punch"),
                dict(kind="pip", s=f(0.66), e=f(0.84), tin="spring"),
                dict(kind="split", s=f(0.84), e=D, tin="split")]
    if variant == "reveal":
        # slow cinematic build: long presenter hold -> reveal screen -> pip
        return [dict(kind="iso1", s=0, e=f(0.34), tin="none"),
                dict(kind="iso2", s=f(0.34), e=f(0.66), tin="zoom"),
                dict(kind="pip", s=f(0.66), e=D, tin="spring")]
    # whip (default)
    return [dict(kind="iso1", s=0, e=f(0.15), tin="none"),
            dict(kind="iso2", s=f(0.15), e=f(0.33), tin="whipL"),
            dict(kind="iso1", s=f(0.33), e=f(0.45), tin="whipR"),
            dict(kind="iso2", s=f(0.45), e=f(0.64), tin="whipL"),
            dict(kind="pip", s=f(0.64), e=f(0.83), tin="spring"),
            dict(kind="split", s=f(0.83), e=D, tin="split")]


OV = 0.35  # incoming overlap for the transition


def emit(scs):
    els, tw = [], []
    for i, sc in enumerate(scs):
        z = 10 + i
        s, e = sc["s"], sc["e"]
        win_s = max(0, round(s - OV, 2)) if sc["tin"] != "none" else s
        dur = round(e - win_s, 2)
        ms = round(win_s, 2)
        k = sc["kind"]
        if k in ("iso1", "iso2"):
            src = "iso1_916.mp4" if k == "iso1" else "iso2_916.mp4"
            eid = f"v{i}"
            els.append(f'<video id="{eid}" class="clip fill" src="{A}/{src}" muted playsinline '
                       f'data-start="{win_s}" data-duration="{dur}" data-track-index="{i}" data-media-start="{ms}" '
                       f'style="z-index:{z}"></video>')
            tw.append(_trans(eid, sc["tin"], s))
        elif k == "pip":
            base, pid = f"v{i}b", f"v{i}p"
            els.append(f'<video id="{base}" class="clip fill" src="{A}/iso2_916.mp4" muted playsinline '
                       f'data-start="{win_s}" data-duration="{dur}" data-track-index="{i}" data-media-start="{ms}" '
                       f'style="z-index:{z}"></video>')
            els.append(f'<video id="{pid}" class="clip pip" src="{A}/iso1_916.mp4" muted playsinline '
                       f'data-start="{s}" data-duration="{round(e - s, 2)}" data-track-index="{i}b" data-media-start="{s}" '
                       f'style="z-index:{z + 40}"></video>')
            tw.append(_trans(base, sc["tin"] if sc["tin"] != "spring" else "zoom", s))
            tw.append(f'tl.fromTo("#{pid}",{{scale:0.1,opacity:0,transformOrigin:"100% 100%"}},'
                      f'{{scale:1,opacity:1,duration:0.5,ease:"back.out(2)"}},{s});')
        elif k == "split":
            tid, bid, did = f"v{i}t", f"v{i}s", f"v{i}d"
            els.append(f'<video id="{tid}" class="clip half-top" src="{A}/iso1_916.mp4" muted playsinline '
                       f'data-start="{s}" data-duration="{round(e - s, 2)}" data-track-index="{i}" data-media-start="{s}" '
                       f'style="z-index:{z}"></video>')
            els.append(f'<video id="{bid}" class="clip half-bot" src="{A}/iso2_169.mp4" muted playsinline '
                       f'data-start="{s}" data-duration="{round(e - s, 2)}" data-track-index="{i}b" data-media-start="{s}" '
                       f'style="z-index:{z}"></video>')
            els.append(f'<div id="{did}" class="clip divider" data-start="{s}" data-duration="{round(e - s, 2)}" '
                       f'data-track-index="{i}c" style="z-index:{z + 5}"></div>')
            tw.append(f'tl.fromTo("#{tid}",{{yPercent:-100}},{{yPercent:0,duration:0.4,ease:"expo.out"}},{s});')
            tw.append(f'tl.fromTo("#{bid}",{{yPercent:100}},{{yPercent:0,duration:0.4,ease:"expo.out"}},{s});')
            tw.append(f'tl.fromTo("#{did}",{{scaleX:0}},{{scaleX:1,duration:0.35,ease:"power2.out"}},{round(s + 0.1, 2)});')
    return "\n    ".join(els), "\n      ".join(tw)


def _trans(eid, tin, t):
    if tin == "whipL":
        return f'tl.fromTo("#{eid}",{{xPercent:100,scale:1.08}},{{xPercent:0,scale:1,duration:0.3,ease:"expo.out"}},{t});'
    if tin == "whipR":
        return f'tl.fromTo("#{eid}",{{xPercent:-100,scale:1.08}},{{xPercent:0,scale:1,duration:0.3,ease:"expo.out"}},{t});'
    if tin == "zoom":
        return f'tl.fromTo("#{eid}",{{scale:1.35,opacity:0}},{{scale:1,opacity:1,duration:0.4,ease:"expo.out"}},{t});'
    if tin == "punch":
        return f'tl.fromTo("#{eid}",{{scale:1.28,opacity:0}},{{scale:1,opacity:1,duration:0.32,ease:"back.out(1.6)"}},{t});'
    if tin == "none":
        return f'tl.set("#{eid}",{{opacity:1}},0);'
    return f'tl.fromTo("#{eid}",{{opacity:0}},{{opacity:1,duration:0.3}},{t});'


def caps():
    h, t = [], []
    for i, cu in enumerate(meta["cues"]):
        s = max(0.0, cu["start"])
        d = max(0.4, round(cu["end"] - s, 2))
        txt = cu["text"].replace("<", "&lt;").replace(">", "&gt;")
        h.append(f'<div id="cap{i}" class="clip cap" data-start="{s}" data-duration="{d}" data-track-index="90"><span>{txt}</span></div>')
        t.append(f'tl.fromTo("#cap{i} span",{{opacity:0,y:36,scale:0.9}},{{opacity:1,y:0,scale:1,duration:0.28,ease:"back.out(2)"}},{s});')
    return "\n    ".join(h), "\n      ".join(t)


els, tw = emit(scenes(VAR, D))
caps_h, caps_t = caps()

TPL = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<title>Animated Reel __TITLE__</title>
<script src="gsap.min.js"></script>
<style>
  @font-face { font-family:"Playfair"; src:url("__A__/../PlayfairDisplay-Italic-var.ttf"); font-weight:400 900; font-style:italic; }
  * { margin:0; padding:0; box-sizing:border-box; }
  #root { position:relative; width:1080px; height:1920px; overflow:hidden; background:#000; }
  .bg { position:absolute; inset:0; background:#000; z-index:0; }
  video.fill { position:absolute; inset:0; width:1080px; height:1920px; object-fit:cover; }
  .pip { position:absolute; right:40px; bottom:250px; width:372px; height:660px; object-fit:cover;
         border:5px solid #fff; border-radius:16px; box-shadow:0 12px 44px rgba(0,0,0,.55); }
  /* face-aware vertical crop so the head is never cut (see hf_frame_fix.py) */
  .half-top { position:absolute; top:0; left:0; width:1080px; height:960px; object-fit:cover; object-position:center __HALFPOS__%; }
  .half-bot { position:absolute; top:1136px; left:0; width:1080px; height:608px; object-fit:cover; }
  .divider { position:absolute; top:957px; left:0; width:1080px; height:6px; background:#fff; transform:scaleX(0); }
  .cap { position:absolute; bottom:158px; left:0; width:1080px; text-align:center; z-index:100; padding:0 60px; }
  .cap span { display:inline-block; font-family:"Playfair", Georgia, serif; font-style:italic; font-weight:800;
              font-size:66px; line-height:1.15; color:__COL__;
              -webkit-text-stroke:5px rgba(0,0,0,.92); paint-order:stroke fill; }
</style>
</head>
<body>
  <div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="__D__">
    <div id="bg" class="bg clip" data-start="0" data-duration="__D__" data-track-index="99"></div>
    __ELS__
    __CAPS__
    <audio id="voice" src="__A__/iso1_916.mp4" data-start="0" data-duration="__D__" data-track-index="80" data-volume="1"></audio>
  </div>
  <script>
    window.__timelines = window.__timelines || {};
    const tl = gsap.timeline({ paused: true });
    __TWEENS__
    __CAPTWEENS__
    window.__timelines["main"] = tl;
  </script>
</body>
</html>
"""

html = (TPL.replace("__TITLE__", f"{meta['speaker']} {meta['id']} {VAR}")
        .replace("__A__", A).replace("__COL__", COL).replace("__D__", str(D))
        .replace("__HALFPOS__", str(meta.get("half_top_pos", 20)))
        .replace("__ELS__", els).replace("__CAPS__", caps_h)
        .replace("__TWEENS__", tw).replace("__CAPTWEENS__", caps_t))
OUT.write_text(html)
print(f"✓ {meta['speaker']} {meta['id']} [{VAR}] -> {OUT} (D={D}s, {len(meta['cues'])} caps)")
