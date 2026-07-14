# Pipeline Plan — Jordan Close Reels

## Goal
6–10 short-form vertical reels cut from both frame-synced ProRes angles, best
angle auto-suggested, fully local.

## Constraints
- Proxy is analysis-only; final pixels come from the T7 ProRes masters.
- Masters share a start timecode → a TwelveLabs offset (seconds) maps 1:1 to both.
- Keep both renders always; angle pick is advisory.
- No public buckets / Drive. No publish unless explicitly told (`oc-exports`).

## Decisions
- **Models:** pegasus1.2 (generative) + marengo2.7 (embedding/search), thumbnail addon.
- **Candidate merge:** highlights (0.85) + chapters (0.6) + search hits (score/confidence),
  snapped to transcript sentence boundaries, clamped 20–45s, de-duped at IoU ≥ 0.5,
  capped at 10 by score.
- **Reframe:** center crop `ih*9/16:ih` → 1080×1920, setsar=1, 0.3s lead/tail pad.
- **Angle heuristic:** largest face scored `0.6*size + 0.4*centering`; tune in `04_pick_angle.py`.
- **Audio:** loudnorm to −14 LUFS.

## Open / tunable
- Face-heuristic weights (`W_SIZE`, `W_CENTER`, `AREA_REFERENCE`) — adjust after eyeballing picks.
- Whether to add "transcription" to search_options for more transcript-driven hits.

## State machine
`analysis/state.json`: `index_id → video_id → status=ready` gate the later steps; each script re-runnable.
