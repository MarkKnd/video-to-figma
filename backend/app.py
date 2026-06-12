"""
Video -> Figma backend (production / hosted).

Local FastAPI service that:
  /analyze  -> pull video metadata (yt-dlp), download a fast proxy, run
               PySceneDetect, and suggest a frame plan + quality.
  /extract  -> download the chosen quality, cut a frame at each chosen
               timestamp with ffmpeg (scaled to a 1920 long edge), and
               serve them as static files for the Figma plugin to fetch.

Hardened for public hosting: per-IP rate limiting, a concurrency gate,
hard caps on duration / frame count, automatic job cleanup, and frame
URLs derived from the public request host (HTTPS on Render).
"""

import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import List, Optional

import yt_dlp
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from scenedetect import detect, ContentDetector

# ----------------------------- config ------------------------------------

PORT = int(os.environ.get("PORT", "8765"))
# If set, frame URLs use this base (e.g. https://video-to-figma.onrender.com).
# Otherwise they are derived from the incoming request host.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

LONG_EDGE = 1920                                  # frame long-side in px
PROXY_HEIGHT = int(os.environ.get("PROXY_HEIGHT", "480"))   # for detection
MAX_DURATION = int(os.environ.get("MAX_DURATION", "1200"))  # 20 min cap
HARD_MAX_FRAMES = int(os.environ.get("HARD_MAX_FRAMES", "60"))
JOB_TTL = int(os.environ.get("JOB_TTL", "1800"))            # 30 min
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "20"))        # analyze/IP/hour
MAX_CONCURRENCY = int(os.environ.get("MAX_CONCURRENCY", "2"))

BASE = Path(__file__).resolve().parent
JOBS = BASE / "_jobs"
JOBS.mkdir(exist_ok=True)

app = FastAPI(title="Video -> Figma backend")

# Figma plugin UIs run in an iframe with a `null` origin, so allow everything.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/frames", StaticFiles(directory=str(JOBS)), name="frames")

CACHE: dict = {}                 # job_id -> metadata
_sema = threading.Semaphore(MAX_CONCURRENCY)
_rate: dict = {}                 # ip -> [timestamps]
_rate_lock = threading.Lock()


# ----------------------------- models ------------------------------------


class AnalyzeIn(BaseModel):
    url: str


class ExtractIn(BaseModel):
    job_id: str
    mode: str = "scene"          # "scene" | "interval"
    interval_seconds: float = 2.0
    quality_height: int = 1080
    max_frames: int = 40


# ----------------------------- helpers -----------------------------------


def _ffmpeg_ok() -> bool:
    return shutil.which("ffmpeg") is not None


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate(ip: str) -> bool:
    now = time.time()
    with _rate_lock:
        recent = [t for t in _rate.get(ip, []) if t > now - 3600]
        if len(recent) >= RATE_LIMIT:
            _rate[ip] = recent
            return False
        recent.append(now)
        _rate[ip] = recent
    return True


def _prune_jobs() -> None:
    now = time.time()
    for d in list(JOBS.iterdir()):
        try:
            if d.is_dir() and now - d.stat().st_mtime > JOB_TTL:
                shutil.rmtree(d, ignore_errors=True)
                CACHE.pop(d.name, None)
        except FileNotFoundError:
            pass


def _base_url(request: Request) -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    return str(request.base_url).rstrip("/")


def _heights_from_info(info: dict) -> List[int]:
    heights = set()
    for f in info.get("formats", []) or []:
        h = f.get("height")
        if h:
            heights.add(int(h))
    if not heights and info.get("height"):
        heights.add(int(info["height"]))
    return sorted(heights, reverse=True)


def _download(url: str, out_tmpl: str, max_height: Optional[int]) -> str:
    fmt = f"best[height<={max_height}]/best" if max_height else "best"
    opts = {
        "format": fmt,
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


def _scene_times(video_path: str) -> List[float]:
    try:
        scenes = detect(video_path, ContentDetector())
    except Exception:
        scenes = []
    times = [0.0]
    for start, _end in scenes:
        s = start.get_seconds()
        if s > 0.5:
            times.append(round(s, 3))
    out: List[float] = []
    for t in sorted(times):
        if not out or t - out[-1] > 0.4:
            out.append(t)
    return out


def _extract_frame(video: str, t: float, out: str) -> None:
    vf = (
        f"scale='if(gt(iw,ih),{LONG_EDGE},-2)':"
        f"'if(gt(iw,ih),-2,{LONG_EDGE})'"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", video,
         "-frames:v", "1", "-vf", vf, "-q:v", "2", out],
        check=True,
        capture_output=True,
    )


def _ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


# ----------------------------- routes ------------------------------------


@app.get("/")
def root():
    return {"service": "video-to-figma", "ok": True}


@app.get("/health")
def health():
    return {"ok": True, "ffmpeg": _ffmpeg_ok()}


@app.post("/analyze")
def analyze(body: AnalyzeIn, request: Request):
    if not _ffmpeg_ok():
        raise HTTPException(500, "ffmpeg is not installed or not on PATH")

    ip = _client_ip(request)
    if not _check_rate(ip):
        raise HTTPException(429, "Rate limit reached. Try again later.")

    _prune_jobs()

    # 1) metadata (no download yet)
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                               "noplaylist": True}) as ydl:
            info = ydl.extract_info(body.url, download=False)
    except Exception as e:
        raise HTTPException(400, f"Could not read video: {e}")

    if info.get("_type") == "playlist" and info.get("entries"):
        info = info["entries"][0]

    duration = float(info.get("duration") or 0)
    if duration and duration > MAX_DURATION:
        raise HTTPException(
            413,
            f"Video is {int(duration)}s; the limit is {MAX_DURATION}s "
            f"({MAX_DURATION // 60} min). Try a shorter clip.",
        )

    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    title = (info.get("title") or "video").strip()
    heights = _heights_from_info(info)
    capped = [h for h in heights if h and h <= 1080]
    recommended_quality = max(capped) if capped else 1080

    job_id = uuid.uuid4().hex[:12]
    job_dir = JOBS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # 2) heavy work (proxy download + scene detection) behind a gate
    if not _sema.acquire(timeout=3):
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(503, "Server busy, please retry in a moment.")
    try:
        try:
            proxy = _download(body.url, str(job_dir / "proxy.%(ext)s"),
                              PROXY_HEIGHT)
        except Exception as e:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(400, f"Could not download video: {e}")
        scenes = _scene_times(proxy)
    finally:
        _sema.release()

    suggested = (scenes if len(scenes) <= HARD_MAX_FRAMES
                 else scenes[:: max(1, len(scenes) // HARD_MAX_FRAMES)])

    CACHE[job_id] = {
        "url": body.url,
        "proxy": proxy,
        "title": title,
        "duration": duration,
        "scenes": scenes,
        "width": width,
        "height": height,
        "heights": heights,
    }

    return {
        "job_id": job_id,
        "title": title,
        "duration": duration,
        "duration_label": _ts(duration),
        "width": width,
        "height": height,
        "aspect": (round(width / height, 4) if height else None),
        "qualities": heights or [recommended_quality],
        "recommended_quality": recommended_quality,
        "scene_count": len(scenes),
        "scene_times": scenes,
        "recommended_mode": "scene",
        "recommended_count": len(suggested),
        "recommended_interval": round(duration / max(1, len(suggested)), 2)
        if duration else 2.0,
        "max_frames_allowed": HARD_MAX_FRAMES,
    }


@app.post("/extract")
def extract(body: ExtractIn, request: Request):
    job = CACHE.get(body.job_id)
    if not job:
        raise HTTPException(404, "Unknown or expired job_id - run /analyze again")

    job_dir = JOBS / body.job_id
    frames_dir = job_dir / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    cap = max(1, min(body.max_frames, HARD_MAX_FRAMES))

    # choose timestamps
    if body.mode == "interval":
        times = []
        t = 0.0
        dur = job["duration"] or 0
        step = max(0.2, body.interval_seconds)
        while (dur == 0 and not times) or t < dur:
            times.append(round(t, 3))
            t += step
            if len(times) >= cap:
                break
    else:
        times = list(job["scenes"])

    if len(times) > cap:
        stride = max(1, len(times) // cap)
        times = times[::stride][:cap]

    want = body.quality_height
    if want <= PROXY_HEIGHT:
        source = job["proxy"]
    else:
        source = job.get(f"src_{want}")
        if not source or not os.path.exists(source):
            if not _sema.acquire(timeout=3):
                raise HTTPException(503, "Server busy, please retry.")
            try:
                source = _download(
                    job["url"], str(job_dir / f"src_{want}.%(ext)s"), want
                )
                job[f"src_{want}"] = source
            except Exception as e:
                raise HTTPException(400, f"Could not download {want}p: {e}")
            finally:
                _sema.release()

    base = _base_url(request)
    frames = []
    for i, t in enumerate(times):
        name = f"{i + 1:04d}.jpg"
        out = frames_dir / name
        try:
            _extract_frame(source, t, str(out))
        except subprocess.CalledProcessError:
            continue
        if not out.exists():
            continue
        frames.append({
            "index": i + 1,
            "t": t,
            "label": _ts(t),
            "url": f"{base}/frames/{body.job_id}/frames/{name}",
        })

    if not frames:
        raise HTTPException(500, "No frames could be extracted")

    return {
        "job_id": body.job_id,
        "title": job["title"],
        "count": len(frames),
        "frames": frames,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
