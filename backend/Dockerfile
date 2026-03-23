FROM python:3.14-slim@sha256:6a27522252aef8432841f224d9baaa6e9fce07b07584154fa0b9a96603af7456

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (separate layer for caching)
COPY python/pyproject.toml python/uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY python/ .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "fast_api:app", "--host", "0.0.0.0", "--port", "8000"]
