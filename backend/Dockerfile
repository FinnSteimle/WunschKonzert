# --- Base Stage (Shared) ---
FROM python:3.14-slim@sha256:6a27522252aef8432841f224d9baaa6e9fce07b07584154fa0b9a96603af7456 AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files
COPY python/pyproject.toml python/uv.lock ./

# Decide whether to install dev dependencies
ARG DEV=false
RUN if [ "$DEV" = "true" ] ; then \
    uv sync --frozen && \
    apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    uv run playwright install --with-deps chromium firefox webkit && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* ; \
    else \
    uv sync --frozen --no-dev ; \
    fi


# --- Test Stage ---
FROM base AS test
# Install dev dependencies (pytest, etc.)
RUN uv sync --frozen
# Copy source code and tests
COPY python/ .
# Usage in CI: docker compose -f compose.test.yaml run --rm api-test uv run pytest ...


# --- Runtime Stage (Final Production) ---
FROM base AS runner
# Copy source code only (production)
COPY python/ .
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
