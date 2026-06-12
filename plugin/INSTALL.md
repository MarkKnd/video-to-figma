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
- Paste a video link → **Analyze** → pick scene-cuts or every-N-seconds and a
  quality → choose the page → **Export to Figma**.
- Screenshots land as a horizontal stack of frames sized to the video's aspect.

## Known limitation
YouTube and X currently block downloads from the hosted server's IP, so those
links may fail with an auth error. Vimeo and many other hosts work. (Fixing
YouTube/X reliably needs paid proxies — deliberately skipped for now.)

Questions → Mark.
