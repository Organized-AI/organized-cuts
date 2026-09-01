# Organized Cuts

Turn a long-form talk into short-form vertical reels — automatically.

Organized Cuts ingests a talk into [TwelveLabs](https://twelvelabs.io) to find the
most shareable moments, then cuts captioned 9:16 reels from frame-synced ProRes
masters with `ffmpeg`. It reframes a presenter camera with a face-tracked crop,
splices in a screen-recording feed as a picture-in-picture during demos, and
burns in styled, word-accurate captions from a local Whisper transcript.

Everything runs locally; nothing is published without you asking.

## Projects

| Project | What it is |
|---------|-----------|
| [`jordan-close/`](jordan-close/) | First pipeline: the Jordan Close workshop talk (presenter ISO1 + screen-recording ISO2 → 15 reels) |

## Pipeline (per project)

```
01 ingest      Create a TwelveLabs index, upload a 720p proxy, poll to ready
02 analyze     Generative highlights + embedding search → candidate clips
   transcript  Local Whisper (faster-whisper) → word-accurate transcript
03 cut         9:16 reels from the masters: face-tracked crop, demo picture-in-
               picture over the screen feed, burned-in captions
04 contact     QA contact sheet
05 loudnorm    Normalize every reel to -14 LUFS
06 report      INDEX.md + summary table
07 widgets     Talk Map widgets from the TwelveLabs analysis
08 talkmap     Merge every session into one Talk Map bundle (all sessions)
```

See [`jordan-close/README.md`](jordan-close/README.md) for the full run guide.

## Talk Map widgets

The [vault](https://recordings.organizedai.vip/vault) already renders a Talk Map
— a SPINE rail and ORBIT dial built from TwelveLabs chapters. Stages 07/08 turn
the same analysis into **widgets** that hang off that map: chapter maps, moments
linked to the cut reels, demo walkthroughs, quotes, takeaways, a Q&A index,
pre-baked Marengo search probes, topic indexes, reel strips, and cross-talk links
between speakers who covered the same ground.

```bash
bash jordan-close/scripts/widgets_all.sh            # every session, then merge
bash jordan-close/scripts/widgets_all.sh --offline  # no API calls
python3 jordan-close/tests/test_widgets.py          # checks, no key needed
```

[`talks/registry.json`](talks/registry.json) maps each session dir to its talk on
recordings.organizedai.vip, and multi-part talks are stitched onto one timeline.
The build writes `talkmap/build/talks/<id>.json`, whose `{total, chapters}` shape
is exactly what the vault's `/api/chapters` serves today — `widgets` is additive.
Full schema in [`docs/TALK-MAP-WIDGETS.md`](docs/TALK-MAP-WIDGETS.md).

## Highlights

- **Subject-aware reframing** — detects the speaker's position per clip (OpenCV)
  and crops 16:9 → 9:16 around them instead of a naive center crop.
- **Demo picture-in-picture** — when the moment is a screen demo, the screen
  feed fills the frame with the presenter kept in a corner inset; audio stays on
  the presenter's mic.
- **Word-accurate captions** — a local Whisper pass gives correct text and
  timing; captions are rendered as styled PNG overlays (works even with a
  minimal `ffmpeg` build that lacks `libass`).

## Requirements

- Source video: the ProRes masters on local disk, **or** `masters_url` in a
  session's `project.json` pointing at hosted copies — `ffmpeg` reads those over
  HTTP range requests, at the cost of a second encode generation. Local wins when
  present. The widget stages (07/08) read no video at all.
- `ffmpeg` (with `h264_videotoolbox` on Apple Silicon)
- Python 3.13 + `pip install -r jordan-close/requirements.txt`
- A TwelveLabs API key (see each project's `.env.example`)
- Caption font: Playfair Display Bold Italic — fetched at setup, e.g.
  ```bash
  curl -fsSL -o jordan-close/assets/fonts/PlayfairDisplay-Italic-var.ttf \
    "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf"
  ```
  (SIL Open Font License. The caption renderer falls back to a system serif if absent.)

## License

Code: MIT (see [LICENSE](LICENSE)). Source video, transcripts, and rendered reels
are not included in this repository.
