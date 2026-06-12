FROM python:3.11-slim

# ffmpeg is required for frame extraction.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

ENV PORT=8765
EXPOSE 8765

# Render injects $PORT. --proxy-headers makes request.base_url reflect the
# public https host so frame URLs are correct.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
