# Install — Video → Figma Screenshots

You only need these 3 files (manifest.json, code.js, ui.html) and the
**Figma desktop app**. No backend or setup — it talks to a hosted service.

## Steps (2 minutes)
1. Unzip this folder somewhere it can stay (don't delete it later).
2. Open the **Figma desktop app** (browser Figma can't run dev plugins).
3. Top menu → **Plugins → Development → Import plugin from manifest…**
4. Select **`manifest.json`** from this folder.
5. Open any file in edit mode → **Plugins → Development → Video to Figma Screenshots**.

## Using it
Two ways to start:
- **Paste link** — works for Vimeo and direct video URLs.
- **Upload file** — pick a video file from your computer (use this for YouTube
  or X: download the clip first, then upload it here).

Then: pick scene-cuts or every-N-seconds → choose the page → **Export to Figma**.
Screenshots land as a horizontal stack of frames sized to the video's aspect.

## Note
Pasting a **YouTube or X link** won't work (those sites block the server).
Just download the clip and use **Upload file** instead. Big files take a little
while to process.

Questions → Mark.
