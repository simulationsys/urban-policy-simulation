# Backend (SUB-05) container.
#
# Build context is the REPOSITORY ROOT, not backend/ — the backend serves the simulation
# core, so the image has to contain it:
#     docker build -f backend/Dockerfile -t uip-backend .
#
# Building from backend/ alone produces an image that can only ever run the stub engine,
# which streams plausible metrics while simulating no citizens at all.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # The simulation package is copied in, not pip-installed, so it must be importable.
    PYTHONPATH=/app/simulation

WORKDIR /app

# Install deps first for better layer caching. The simulation core needs a compiler-free
# scientific stack (mesa, networkx, pandas, pyarrow); osmnx is intentionally NOT installed
# because the graph is prepared offline by data/pipelines and shipped as GraphML.
COPY backend/pyproject.toml ./backend/pyproject.toml
RUN pip install --upgrade pip \
    && pip install ./backend \
    && pip install "mesa>=2.2.0" "numpy>=1.24.0" "networkx>=3.0" "pandas>=2.0.0" "pyarrow>=15.0.0"

# App code + the simulation core it drives.
COPY backend/app ./app
COPY simulation/simulation ./simulation/simulation

# Processed street/population data. Optional: if the directory is empty the engine falls
# back to its synthetic grid rather than failing (see Settings.resolve_engine_kind).
COPY data/processed_data ./data/processed_data

# SQLite metadata + any local artifacts live here; mount a volume in prod to persist.
RUN mkdir -p /app/data

EXPOSE 8000

# Honor the platform's $PORT if provided (Railway/Render inject it), else 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
