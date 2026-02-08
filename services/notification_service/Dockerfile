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
COPY services/notification_service/pyproject.toml services/notification_service/pyproject.toml

# Create minimal package structures for install
RUN mkdir -p shared/src/shared && touch shared/src/shared/__init__.py && \
    mkdir -p services/notification_service/src/notification_service && touch services/notification_service/src/notification_service/__init__.py

# Install dependencies (cached unless pyproject.toml changes)
RUN uv sync --project services/notification_service --no-dev

# --- Runtime ---
FROM base AS runtime

COPY --from=deps /app /app

# Copy actual source code
COPY shared/src shared/src
COPY services/notification_service/src services/notification_service/src

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "notification_service"]
