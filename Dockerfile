# syntax=docker/dockerfile:1

# ---- Builder: install dependencies into a .venv with uv ----
FROM python:3.12-slim-bookworm AS builder

# uv for fast, lockfile-based installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

# Build deps for psycopg2 (source build needs pg_config + a compiler)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (cached layer) using only the lock + manifest
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Then add the project source and install it
COPY . /app
RUN uv sync --frozen --no-dev

# ---- Runtime: slim image with just the venv + libpq ----
FROM python:3.12-slim-bookworm

# Runtime shared library for psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring over the built virtualenv and the application code
COPY --from=builder /app /app

# Put the venv on PATH so `uvicorn`/`python` resolve to it
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Railway injects $PORT; default to 8000 for local runs
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
