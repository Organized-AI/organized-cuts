#!/usr/bin/env python3
"""Build one demo clip in a chosen STYLE (signature-look exploration).
Fixed transition arc so styles are compared on aesthetic, not motion.

Styles: editorial | kinetic | cinematic | hud
    ./.venv/bin/python scripts/hf_style.py <asset_dir_rel> <out_html> <style>
"""
import json
import sys
import pathlib

A = sys.argv[1]
OUT = pathlib.Path(sys.argv[2])
STYLE = sys.argv[3] if len(sys.argv) > 3 else "editorial"
meta = json.loads((OUT.parent / A / "meta.json").read_text())
D = meta["duration"]
r, g, b = meta["color"]
COL = f"rgb({r},{g},{b})"
f = lambda x: round(x * D, 2)

# fixed arc
SCENES = [("iso1", 0, f(0.16), "none"), ("iso2", f(0.16), f(0.5), "whipL"),
          ("pip", f(0.5), f(0.78), "zoom"), ("split", f(0.78), D, "split")]
OV = 0.35


def _tin(eid, tin, t):
    m = {"whipL": f'tl.fromTo("#{eid}",{{xPercent:100,scale:1.08}},{{xPercent:0,scale:1,duration:0.3,ease:"expo.out"}},{t});',
         "zoom": f'tl.fromTo("#{eid}",{{scale:1.3,opacity:0}},{{scale:1,opacity:1,duration:0.4,ease:"expo.out"}},{t});',
         "none": f'tl.set("#{eid}",{{opacity:1}},0);'}
    return m.get(tin, f'tl.fromTo("#{eid}",{{opacity:0}},{{opacity:1,duration:0.3}},{t});')


def emit():
    els, tw = [], []
    for i, (k, s, e, tin) in enumerate(SCENES):
        z = 10 + i
        ws = max(0, round(s - OV, 2)) if tin != "none" else s
        dur = round(e - ws, 2)
        if k in ("iso1", "iso2"):
            src = "iso1_916.mp4" if k == "iso1" else "iso2_916.mp4"
            eid = f"v{i}"
            els.append(f'<video id="{eid}" class="clip fill grade" src="{A}/{src}" muted playsinline data-start="{ws}" data-duration="{dur}" data-track-index="{i}" data-media-start="{ws}" style="z-index:{z}"></video>')
            tw.append(_tin(eid, tin, s))
        elif k == "pip":
            els.append(f'<video id="v{i}b" class="clip fill grade" src="{A}/iso2_916.mp4" muted playsinline data-start="{ws}" data-duration="{dur}" data-track-index="{i}" data-media-start="{ws}" style="z-index:{z}"></video>')
            els.append(f'<video id="v{i}p" class="clip pip grade" src="{A}/iso1_916.mp4" muted playsinline data-start="{s}" data-duration="{round(e-s,2)}" data-track-index="{i}b" data-media-start="{s}" style="z-index:{z+40}"></video>')
            tw.append(_tin(f"v{i}b", tin, s))
            tw.append(f'tl.fromTo("#v{i}p",{{scale:0.1,opacity:0,transformOrigin:"100% 100%"}},{{scale:1,opacity:1,duration:0.5,ease:"back.out(2)"}},{s});')
        else:
            els.append(f'<video id="v{i}t" class="clip half-top grade" src="{A}/iso1_916.mp4" muted playsinline data-start="{s}" data-duration="{round(e-s,2)}" data-track-index="{i}" data-media-start="{s}" style="z-index:{z}"></video>')
            els.append(f'<video id="v{i}s" class="clip half-bot grade" src="{A}/iso2_169.mp4" muted playsinline data-start="{s}" data-duration="{round(e-s,2)}" data-track-index="{i}b" data-media-start="{s}" style="z-index:{z}"></video>')
            els.append(f'<div id="v{i}d" class="clip divider" data-start="{s}" data-duration="{round(e-s,2)}" data-track-index="{i}c" style="z-index:{z+5}"></div>')
            tw.append(f'tl.fromTo("#v{i}t",{{yPercent:-100}},{{yPercent:0,duration:0.4,ease:"expo.out"}},{s});')
            tw.append(f'tl.fromTo("#v{i}s",{{yPercent:100}},{{yPercent:0,duration:0.4,ease:"expo.out"}},{s});')
            tw.append(f'tl.fromTo("#v{i}d",{{scaleX:0}},{{scaleX:1,duration:0.35}},{round(s+0.1,2)});')
    return "\n    ".join(els), "\n      ".join(tw)


# ---- style presets ----------------------------------------------------------
GRAIN = "url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22200%22><filter id=%22n%22><feTurbulence type=%22fractalNoise%22 baseFrequency=%220.9%22 numOctaves=%222%22 stitchTiles=%22stitch%22/></filter><rect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23n)%22 opacity=%220.5%22/></svg>')"


def style():
    if STYLE == "kinetic":
        return dict(grade="saturate(1.32) contrast(1.14)",
                    overlay="", overlay_css="",
                    capwrap="bottom:210px; display:flex; justify-content:center;",
                    capspan=f"font-family:Anton,Impact,sans-serif; font-size:88px; line-height:1.0; text-transform:uppercase; letter-spacing:1px; color:#fff; background:{COL}; padding:8px 26px; border-radius:8px; box-shadow:0 10px 40px rgba(0,0,0,.45);",
                    word=True,
                    caption_in=lambda i, s: f'tl.from("#cap{i} .w",{{opacity:0,y:40,scale:0.6,duration:0.26,stagger:0.05,ease:"back.out(2.4)"}},{s});',
                    fonts='@font-face{font-family:Anton;src:url("__A__/../Anton-Regular.ttf");}')
    if STYLE == "cinematic":
        return dict(grade="contrast(1.14) saturate(0.9) sepia(0.14) brightness(0.97)",
                    overlay='<div class="clip ov grain" data-start="0" data-duration="__D__" data-track-index="70"></div>'
                            '<div class="clip ov vig" data-start="0" data-duration="__D__" data-track-index="71"></div>'
                            '<div class="clip ov barT" data-start="0" data-duration="__D__" data-track-index="72"></div>'
                            '<div class="clip ov barB" data-start="0" data-duration="__D__" data-track-index="73"></div>',
                    overlay_css=f".grain{{background-image:{GRAIN};background-size:300px;mix-blend-mode:overlay;opacity:.14;z-index:60;}}"
                                ".vig{box-shadow:inset 0 0 460px 120px rgba(0,0,0,.72);z-index:61;}"
                                ".barT{top:0;height:140px;background:#000;z-index:62;}.barB{bottom:0;height:140px;background:#000;z-index:62;}",
                    capwrap="bottom:210px; text-align:center;",
                    capspan="font-family:Playfair,serif; font-style:italic; font-weight:700; font-size:58px; letter-spacing:2px; color:#f5f0e6; text-shadow:0 2px 18px rgba(0,0,0,.8);",
                    word=False,
                    caption_in=lambda i, s: f'tl.fromTo("#cap{i} span",{{opacity:0,letterSpacing:"14px"}},{{opacity:1,letterSpacing:"2px",duration:0.5,ease:"power2.out"}},{s});',
                    fonts='')
    if STYLE == "hud":
        return dict(grade="contrast(1.2) saturate(0.7) brightness(0.95)",
                    overlay='<div class="clip ov grid" data-start="0" data-duration="__D__" data-track-index="70"></div>'
                            '<div class="clip ov br brtl" data-start="0" data-duration="__D__" data-track-index="71"></div>'
                            '<div class="clip ov br brtr" data-start="0" data-duration="__D__" data-track-index="72"></div>'
                            '<div class="clip ov br brbl" data-start="0" data-duration="__D__" data-track-index="73"></div>'
                            '<div class="clip ov br brbr" data-start="0" data-duration="__D__" data-track-index="74"></div>',
                    overlay_css=".grid{background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);background-size:90px 90px;z-index:60;}"
                                ".br{width:70px;height:70px;z-index:61;border-color:%s;border-style:solid;border-width:0;}" % COL
                                + ".brtl{top:40px;left:40px;border-top-width:4px;border-left-width:4px;}.brtr{top:40px;right:40px;border-top-width:4px;border-right-width:4px;}"
                                + ".brbl{bottom:40px;left:40px;border-bottom-width:4px;border-left-width:4px;}.brbr{bottom:40px;right:40px;border-bottom-width:4px;border-right-width:4px;}",
                    capwrap="bottom:220px; text-align:center;",
                    capspan=f"font-family:'JetBrains Mono',monospace; font-weight:700; font-size:46px; text-transform:uppercase; letter-spacing:1px; color:{COL}; text-shadow:0 0 14px {COL},0 0 4px {COL}; background:rgba(0,0,0,.45); padding:8px 20px;",
                    word=False,
                    caption_in=lambda i, s: f'tl.fromTo("#cap{i} span",{{opacity:0}},{{opacity:1,duration:0.12}},{s});',
                    fonts="@font-face{font-family:'JetBrains Mono';src:url('__A__/../JetBrainsMono.ttf');font-weight:100 800;}")
    # editorial (default)
    return dict(grade="none", overlay="", overlay_css="",
                capwrap="bottom:170px; text-align:center;",
                capspan=f"font-family:Playfair,serif; font-style:italic; font-weight:800; font-size:66px; line-height:1.15; color:{COL}; -webkit-text-stroke:5px rgba(0,0,0,.92); paint-order:stroke fill;",
                word=False,
                caption_in=lambda i, s: f'tl.fromTo("#cap{i} span",{{opacity:0,y:36,scale:0.9}},{{opacity:1,y:0,scale:1,duration:0.28,ease:"back.out(2)"}},{s});',
                fonts='')


ST = style()


def caps():
    h, t = [], []
    for i, cu in enumerate(meta["cues"]):
        s = max(0.0, cu["start"]); dur = max(0.4, round(cu["end"] - s, 2))
        txt = cu["text"].replace("<", "&lt;").replace(">", "&gt;")
        if ST["word"]:
            inner = " ".join(f'<span class="w">{w}</span>' for w in txt.split())
        else:
            inner = f"<span>{txt}</span>"
        h.append(f'<div id="cap{i}" class="clip cap" data-start="{s}" data-duration="{dur}" data-track-index="90">{inner}</div>')
        t.append(ST["caption_in"](i, s))
    return "\n    ".join(h), "\n      ".join(t)


els, tw = emit()
caps_h, caps_t = caps()
fonts = '@font-face{font-family:"Playfair";src:url("__A__/../PlayfairDisplay-Italic-var.ttf");font-weight:400 900;font-style:italic;}' + ST["fonts"]

TPL = """<!doctype html><html lang="en"><head>
<meta charset="UTF-8" /><meta name="viewport" content="width=1080, height=1920" />
<title>Style __STYLE__</title>
<script src="gsap.min.js"></script>
<style>
  __FONTS__
  * { margin:0; padding:0; box-sizing:border-box; }
  #root { position:relative; width:1080px; height:1920px; overflow:hidden; background:#000; }
  .bg { position:absolute; inset:0; background:#000; z-index:0; }
  video.fill { position:absolute; inset:0; width:1080px; height:1920px; object-fit:cover; }
  .grade { filter: __GRADE__; }
  .pip { position:absolute; right:40px; bottom:250px; width:372px; height:660px; object-fit:cover; border:5px solid #fff; border-radius:16px; box-shadow:0 12px 44px rgba(0,0,0,.55); }
  /* face-aware vertical crop so the head is never cut (see hf_frame_fix.py) */
  .half-top { position:absolute; top:0; left:0; width:1080px; height:960px; object-fit:cover; object-position:center __HALFPOS__%; }
  .half-bot { position:absolute; top:1136px; left:0; width:1080px; height:608px; object-fit:cover; }
  .divider { position:absolute; top:957px; left:0; width:1080px; height:6px; background:#fff; transform:scaleX(0); }
  .ov { position:absolute; inset:0; }
  __OVCSS__
  .cap { position:absolute; left:0; width:1080px; z-index:100; padding:0 60px; __CAPWRAP__ }
  .cap span, .cap .w { display:inline-block; __CAPSPAN__ }
  .cap .w { margin:0 6px; }
</style></head>
<body>
  <div id="root" data-composition-id="main" data-start="0" data-width="1080" data-height="1920" data-duration="__D__">
    <div id="bg" class="bg clip" data-start="0" data-duration="__D__" data-track-index="99"></div>
    __ELS__
    __OVERLAY__
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
</body></html>"""

html = (TPL.replace("__STYLE__", STYLE).replace("__FONTS__", fonts).replace("__GRADE__", ST["grade"])
        .replace("__OVCSS__", ST["overlay_css"]).replace("__CAPWRAP__", ST["capwrap"]).replace("__CAPSPAN__", ST["capspan"])
        .replace("__ELS__", els).replace("__OVERLAY__", ST["overlay"]).replace("__CAPS__", caps_h)
        .replace("__TWEENS__", tw).replace("__CAPTWEENS__", caps_t)
        .replace("__HALFPOS__", str(meta.get("half_top_pos", 20)))
        .replace("__D__", str(D)).replace("__A__", A))
OUT.write_text(html)
print(f"✓ style [{STYLE}] -> {OUT}")
