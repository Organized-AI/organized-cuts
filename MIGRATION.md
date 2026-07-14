# Migrating Organized Cuts to claws-mac-mini

Move the reel pipeline off the M1 MBP onto **claws-mac-mini** so the batch runs
there and the laptop is free. The only hard dependency is the **T7 SSD** (the
150 GB of ProRes masters) — it must be physically on the Mini.

Facts gathered from the MBP (2026-07-13):
- Masters: `/Volumes/T7/Vol 2 Workshop/…` (exFAT — mounts on any Mac at the same path)
- Mini on Tailscale: `claws-mac-mini` = `100.82.244.127`, user **jordan@**
- MBP SSH key to authorize: `~/.ssh/id_ed25519.pub` (`ssh-ed25519 …0o91cE gitlab key`)
- rclone remote `gdrive` (Shared-Drive scoped, has OAuth token): `~/.config/rclone/rclone.conf` (557 B)
- Whisper large-v3 already cached: `~/.cache/huggingface` (4.3 GB)
- Project code + data: `/Users/supabowl/organized-cuts` (1.8 GB, minus `.venv`)

---

## Step 0 — Physical + access (you, tomorrow)

1. **Move T7**: eject from the MBP, plug into claws-mac-mini. Confirm it mounts:
   `ls "/Volumes/T7/Vol 2 Workshop"` → should list the Session folders.
2. **Enable SSH** to the Mini (pick one):
   - Tailscale SSH: on the Mini run `tailscale up --ssh`, then `ssh jordan@claws-mac-mini` works from the MBP; **or**
   - Classic SSH: System Settings → General → Sharing → **Remote Login = On**, then append the MBP key to the Mini:
     ```bash
     # run on the MBP:
     ssh-copy-id -i ~/.ssh/id_ed25519.pub jordan@100.82.244.127
     ```
   Verify: `ssh jordan@claws-mac-mini 'echo ok; sw_vers'`

---

## Step 1 — Sync code + data + model (from the MBP)

Rsync over Tailscale (brings proxies, transcripts, clips, state → resume is
idempotent). Exclude the machine-specific venv.

```bash
# on the MBP
MINI=jordan@claws-mac-mini
rsync -av --exclude '.venv/' /Users/supabowl/organized-cuts/  "$MINI:~/organized-cuts/"
rsync -av ~/.config/rclone/rclone.conf                        "$MINI:~/.config/rclone/rclone.conf"   # gdrive token
rsync -av ~/.cache/huggingface/                                "$MINI:~/.cache/huggingface/"          # skip 3GB large-v3 re-download
```

`jordan-close/.env` (the TwelveLabs key) travels with the first rsync — confirm
`ssh $MINI 'grep -c TWELVELABS ~/organized-cuts/jordan-close/.env'` returns 1.

## Step 2 — Environment on the Mini (one-time)

```bash
ssh jordan@claws-mac-mini
cd ~/organized-cuts/jordan-close
bash scripts/setup_mini.sh          # ffmpeg check, venv, python deps, Playfair font, rclone binary
```

`setup_mini.sh` verifies `ffmpeg` has `h264_videotoolbox`; if missing:
`brew install ffmpeg` (Homebrew works on the Mini if its Xcode CLT is current).

## Step 3 — Resume / run the batch (on the Mini)

Only the sessions that did **not** finish on the MBP need running. Check what's
done first (completed sessions are already uploaded to Drive):

```bash
grep DONE /tmp/pipetest/batch.log            # on the MBP, before you leave, note completed sessions
# or check Drive: each finished session has a "… — Reels" subfolder with 6-10 files
```

Then on the Mini, edit `scripts/batch_all.sh` `SESSIONS=(…)` down to the
remaining ones and:

```bash
cd ~/organized-cuts/jordan-close
bash scripts/batch_all.sh 2>&1 | tee /tmp/batch_mini.log
```

Or run one session at a time: `bash scripts/run_session.sh ~/organized-cuts/session-1-esteban`

## Step 4 — Verify

Each session self-verifies (`rclone check` → "0 differences"). Spot check a reel:
```bash
ls ~/organized-cuts/session-1-esteban/reels/reel_*.mp4
```

---

## Notes

- **Idempotent**: `prepare_media` skips existing proxy/audio; `01_ingest` reuses
  the TwelveLabs index by name and skips upload if the video is already `ready`;
  `run_session.sh` keeps an existing `clips.json`. So a re-run is cheap.
- **Paths are portable**: `MASTERS` in each `project.json` are absolute
  `/Volumes/T7/…` paths — identical on the Mini once T7 is attached.
- **Secrets**: `.env` (TwelveLabs key) and `rclone.conf` (Drive token) are the
  only sensitive files; they move via the rsyncs above and are gitignored.
- **Whisper model**: rsyncing `~/.cache/huggingface` avoids the 3 GB large-v3
  re-download; otherwise it downloads on first run.
- **Don't run both machines at once** against the same TwelveLabs indexes /
  Drive folders. Finish or stop the MBP batch before starting the Mini.
