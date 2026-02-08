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
COPY services/event_gateway/pyproject.toml services/event_gateway/pyproject.toml

# Create minimal package structures for install
RUN mkdir -p shared/src/shared && touch shared/src/shared/__init__.py && \
    mkdir -p services/event_gateway/src/event_gateway && touch services/event_gateway/src/event_gateway/__init__.py

# Install dependencies (cached unless pyproject.toml changes)
RUN uv sync --project services/event_gateway --no-dev

# --- Runtime ---
FROM base AS runtime

COPY --from=deps /app /app

# Copy actual source code
COPY shared/src shared/src
COPY services/event_gateway/src services/event_gateway/src

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["gunicorn", "event_gateway.wsgi:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
