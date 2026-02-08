FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# --- Dependencies layer ---
FROM base AS deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace root and shared package manifests
COPY pyproject.toml ./
COPY shared/pyproject.toml shared/pyproject.toml

# Create minimal package structure for install
RUN mkdir -p shared/src/shared && touch shared/src/shared/__init__.py

# Install shared with migrations extra (alembic + psycopg2-binary)
RUN uv sync --project shared --extra migrations --no-dev

# --- Runtime ---
FROM base AS runtime

COPY --from=deps /app /app

# Copy shared source and alembic config/migrations
COPY shared/src shared/src
COPY shared/alembic.ini shared/alembic.ini
COPY shared/alembic shared/alembic

ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app/shared

CMD ["alembic", "upgrade", "head"]
