FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# --- Dependencies layer ---
FROM base AS deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace root and dependency manifests
COPY pyproject.toml ./
COPY shared/pyproject.toml shared/pyproject.toml
COPY services/delivery_worker/pyproject.toml services/delivery_worker/pyproject.toml

# Create minimal package structures for install
RUN mkdir -p shared/src/shared && touch shared/src/shared/__init__.py && \
    mkdir -p services/delivery_worker/src/delivery_worker && touch services/delivery_worker/src/delivery_worker/__init__.py

# Install dependencies (cached unless pyproject.toml changes)
RUN uv sync --project services/delivery_worker --no-dev

# --- Runtime ---
FROM base AS runtime

COPY --from=deps /app /app

# Copy actual source code
COPY shared/src shared/src
COPY services/delivery_worker/src services/delivery_worker/src

ENV PATH="/app/.venv/bin:$PATH"

CMD ["celery", "-A", "delivery_worker", "worker", "--loglevel=info"]
