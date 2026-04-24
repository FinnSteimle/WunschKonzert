# System Test Setup

## Install Playwright Dependencies

Add Playwright to your project dependencies:

```bash
cd backend/python
uv add --dev playwright pytest-playwright
uv run playwright install chromium
```

This will:
1. Add `playwright` and `pytest-playwright` to dev dependencies in `pyproject.toml`
2. Install the Chromium browser for Playwright

## Verify Installation

```bash
uv run playwright --version
```

## Run Tests

From project root:
```bash
make test-system
```

This target applies `compose.system.yaml` so system tests run with deterministic
container-internal mapping:

- Frontend -> Backend API: `http://api:8000`
- Frontend -> Backend WebSocket: `ws://api:8000`
- Playwright -> Frontend: `http://frontend:3000`

Because frontend URLs are compiled into the bundle, `compose.system.yaml` also sets
these values as Docker build args to keep runtime and compiled mapping consistent.

Or directly:
```bash
cd backend/python
uv run pytest tests/system/ -v -m system
```

For the Docker-based `make test-system` path, only the mapping smoke suite is executed:

```bash
uv run pytest tests/system/test_stack_mapping.py -v -m system
```
