# Video → Figma Screenshots

Paste a video link (X, YouTube, Vimeo, …), pick a frame plan, and drop the
screenshots into Figma as a horizontal stack of frames sized to the video's
native aspect ratio.

Two parts that run on your Mac:

- **`backend/`** — a local Python service that downloads the video (`yt-dlp`),
  detects scene cuts (`PySceneDetect`), and extracts frames (`ffmpeg`).
- **`plugin/`** — a Figma plugin: the UI panel + the code that places frames.

Nothing is hosted; everything stays on your machine.

---

## One-time setup

Already installed during the build: `ffmpeg`, `yt-dlp`, `scenedetect`,
`fastapi`, `uvicorn`. If you ever move to a new machine:

```bash
brew install ffmpeg
pip3 install -r backend/requirements.txt
```

### Load the Figma plugin (once)

1. Open the **Figma desktop app** (dev plugins don't work in the browser).
2. Menu → **Plugins → Development → Import plugin from manifest…**
3. Choose `plugin/manifest.json` in this folder.

It now appears under **Plugins → Development → Video to Figma Screenshots**.

---

## Each time you use it

1. **Start the backend** (leave this terminal open):

   ```bash
   ./backend/run.sh
   ```

   It serves on `http://localhost:8765`. Check it with
   `curl http://localhost:8765/health` → `{"ok":true,"ffmpeg":true}`.

2. Open your target Figma file (e.g. **Skale | Inspiration**) in the desktop
   app, in **edit mode**.
3. Run the plugin: **Plugins → Development → Video to Figma Screenshots**.
4. Paste the video link → **Analyze**. It suggests a frame count (scene cuts)
   and quality.
5. Tweak: scene-cuts vs. every-N-seconds, count/interval, quality, and the
   target page (or type a new page name).
6. **Export to Figma**. Frames land as a horizontal auto-layout stack on the
   chosen page, and the panel reports the stack width plus any earlier exports
   / duplicates of the same video it found on that page.

---

## How the 7 steps map to the build

| Step | Where |
|---|---|
| 1. Send link | plugin URL field → backend `yt-dlp` |
| 2. Suggest frame rate + quality | `/analyze`: PySceneDetect cuts + format list |
| 3. Change settings | plugin panel (mode / count / interval / quality) |
| 4. Select destination | page picker (existing or new page in current file) |
| 5. Edit access | plugin only runs in an editable file; placement is guarded |
| 6. Horizontal stack, video aspect | frames scaled to 1920 long edge, auto-layout row |
| 7. Space + artefact checks | clear-region placement; scans page for prior `vtf`-tagged exports + same-video duplicates |

---

## Notes & limits

- **Figma "workspace" = the open file.** A plugin runs inside whatever file you
  have open; it can target any **page** in that file (and create new pages), but
  can't browse to other files for you.
- **Login-gated / DRM video** (private posts, paid Vimeo) may not download — the
  panel shows a clear error instead of failing silently.
- Downloading from some platforms can conflict with their Terms of Service;
  this is intended for personal/internal use.
- Extracted frames are cached under `backend/_jobs/<id>/`. Safe to delete
  anytime to reclaim disk.

## API (for reference / scripting)

- `GET /health`
- `POST /analyze` `{ "url": "..." }` → metadata, qualities, scene times, suggestions, `job_id`
- `POST /extract` `{ "job_id", "mode": "scene|interval", "interval_seconds", "quality_height", "max_frames" }` → frame URLs
