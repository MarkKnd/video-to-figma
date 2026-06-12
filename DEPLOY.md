# Deploy & Publish

Two stages: **(A)** host the backend on Render, **(B)** publish the plugin to
the Figma Community.

---

## A. Host the backend on Render

### 1. Push this folder to GitHub
A git repo is already initialized locally. Create an empty GitHub repo, then:

```bash
cd ~/Desktop/video-to-figma
git remote add origin git@github.com:<you>/video-to-figma.git
git push -u origin main
```

### 2. Create the Render service
- Render → **New + → Blueprint** → pick this repo. It reads `render.yaml`
  (Docker build, installs ffmpeg, `plan: standard`).
- Or **New + → Web Service → Docker** pointing at the repo root.
- Wait for the build, then note the URL, e.g. `https://video-to-figma.onrender.com`.

### 3. Smoke-test the live backend
```bash
curl https://YOUR-SERVICE.onrender.com/health         # {"ok":true,"ffmpeg":true}
curl -X POST https://YOUR-SERVICE.onrender.com/analyze \
  -H "Content-Type: application/json" \
  -d '{"url":"https://x.com/interaction/status/2062575428213285352?s=20"}'
```

### 4. Point the plugin at it
Replace `https://YOUR-SERVICE.onrender.com` in **two** files:
- `plugin/ui.html` → the `const API = ...` line
- `plugin/manifest.json` → `networkAccess.allowedDomains`

Both must be the **same https URL**. (Published plugins can't use http or localhost.)

### Tunables (Render → Environment)
| Var | Default | Meaning |
|---|---|---|
| `MAX_DURATION` | 1200 | reject videos longer than this (seconds) |
| `HARD_MAX_FRAMES` | 60 | absolute cap on screenshots per export |
| `RATE_LIMIT` | 20 | analyze requests per IP per hour |
| `MAX_CONCURRENCY` | 2 | simultaneous heavy jobs |
| `PROXY_HEIGHT` | 480 | resolution used for scene detection |
| `JOB_TTL` | 1800 | seconds before extracted frames are deleted |
| `PUBLIC_BASE_URL` | (auto) | only set if using a custom domain |

---

## B. Publish to the Figma Community

In the **Figma desktop app**, with the plugin imported as a development plugin:

1. **Plugins → Development → Video to Figma Screenshots → Publish…**
   (or right-click the plugin in the menu → Publish).
2. Fill the listing:
   - **Name:** Video → Figma Screenshots
   - **Tagline / description:** see `PUBLISH.md` draft text
   - **Icon:** 128×128 PNG (required)
   - **Cover art:** 1920×960 PNG (required)
   - **Tags:** video, screenshots, frames, storyboard, reference
   - **Support contact:** an email you monitor
3. Submit. Figma runs a short review (usually < a day). Updates are published
   the same way and re-reviewed.

### Before you submit — things reviewers/users will hit
- **The backend must be live and warm.** On Render free/spun-down instances the
  first call cold-starts (slow) and frame files are wiped on restart — use a
  paid, always-on instance.
- **Datacenter-IP blocking:** X/YouTube may throttle or block downloads from
  Render's IPs ("confirm you're not a bot"). If users report failures, the fix
  is supplying platform cookies or routing yt-dlp through a residential proxy —
  both add cost/ops. Test several real links from the deployed service first.
- **ToS/abuse:** keep the caps above conservative. Consider adding a short
  disclaimer in the listing that users are responsible for the content they
  process.

---

## Local development
Run the backend locally and temporarily set both placeholders back to
`http://localhost:8765`:

```bash
./backend/run.sh
```
