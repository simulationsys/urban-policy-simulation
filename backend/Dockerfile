# Backend (SUB-05) container. Single-stage, slim — the v1 demo runs on a laptop or a small
# Railway/Render instance (PROJECT_SPEC §4.3, §5.3). No Postgres client, no build toolchain needed.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for better layer caching.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# App code.
COPY app ./app

# SQLite metadata + any local artifacts live here; mount a volume in prod to persist.
RUN mkdir -p /app/data

EXPOSE 8000

# Honor the platform's $PORT if provided (Railway/Render inject it), else 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
