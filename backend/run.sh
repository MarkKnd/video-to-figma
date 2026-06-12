#!/usr/bin/env bash
# Start the Video -> Figma backend on http://localhost:8765
# Ensures Homebrew's ffmpeg is on PATH.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")"
exec python3 app.py
