# API image: FastAPI + ffmpeg (audio transcode) + Alembic migrations on boot.
# Build from the repo root:  docker build -t vani-guard-api .
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY apps/api /app/apps/api
COPY config /app/config
RUN pip install --no-cache-dir "/app/apps/api[postgres]"
ENV PYTHONUNBUFFERED=1 VANI_DEV=0
WORKDIR /app/apps/api
EXPOSE 8000
# migrations first (idempotent), then serve; the app refuses to start if env/pricing are incomplete
CMD ["sh", "-c", "alembic upgrade head && uvicorn vani.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
