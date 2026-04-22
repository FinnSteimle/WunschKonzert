# Makefile for Wunschkonzert Backend
# Usage: make <target>
# Run "make help" to see available targets

.PHONY: help
help:
	@echo "Available targets (Docker-based workflow):"
	@echo ""
	@echo "Development:"
	@echo "  install       - Build and start containers"
	@echo "  run           - Run development server with containers and apply migrations"
	@echo ""
	@echo "Database (via Docker):"
	@echo "  migrate       - Apply all migrations in container"
	@echo "  migrate-make  - Create new migration (M=message)"
	@echo "  migrate-down  - Rollback last migration"
	@echo "  migrate-reset - Reset all migrations"
	@echo ""
	@echo "Code Quality (via Docker):"
	@echo "  lint          - Run linter in container"
	@echo "  format        - Format code in container"
	@echo "  type-check    - Run type checking in container"
	@echo ""
	@echo "Testing (via Docker):"
	@echo "  test          - Run tests in container"
	@echo "  test-cov      - Run tests with coverage in container"
	@echo "  test-system   - Run end-to-end system tests with Playwright"
	@echo ""

	@echo "Cleanup (Docker):"
	@echo "  clean         - Stop containers and remove Docker artifacts, Python cache, node modules, and build files"
	@echo ""
	@echo "Utilities (via Docker):"
	@echo "  shell         - Open Python shell in container"
	@echo "  check-health  - Check API health endpoint"
	@echo "  check-modular - Automatically verify that backend and frontend can run independently"
	@echo ""
	@echo "Independent Services:"
	@echo "  run-backend   - Start only backend services"
	@echo "  run-frontend  - Start only frontend services"

# Development targets (Docker-based)
.PHONY: install
install:
	docker compose -f compose.yaml build && docker compose -f compose.yaml up -d

.PHONY: run
run:
	docker compose -f compose.yaml up --build -d
	docker compose -f compose.yaml exec -T api uv run python -m alembic upgrade head
	docker compose -f compose.yaml logs -f api

.PHONY: run-backend
run-backend:
	docker compose -f backend/compose.yaml up --build -d

.PHONY: run-frontend
run-frontend:
	docker compose -f frontend/compose.yaml up --build -d

.PHONY: check-modular
check-modular:
	./scripts/check_independent.sh


# Database migration targets (Docker-based)
.PHONY: migrate
migrate:
	docker compose -f compose.yaml exec -T api uv run python -m alembic upgrade head

.PHONY: migrate-make
migrate-make:
	docker compose -f compose.yaml exec -T api uv run python -m alembic revision --autogenerate -m "$(M)"

.PHONY: migrate-down
migrate-down:
	docker compose -f compose.yaml exec -T api uv run python -m alembic downgrade -1

.PHONY: migrate-reset
migrate-reset:
	docker compose -f compose.yaml exec -T api uv run python -m alembic downgrade base

# Code quality targets (Docker-based)
.PHONY: lint
lint:
	docker compose -f compose.yaml exec -T api uv run python -m ruff check .

.PHONY: format
format:
	docker compose -f compose.yaml exec -T api uv run python -m ruff format .

.PHONY: type-check
type-check:
	docker compose -f compose.yaml exec -T api uv run python -m mypy .

# Testing targets (Docker-based)
.PHONY: test
test:
	docker compose -f compose.yaml exec -T api uv run python -m pytest -m "not system" -q --junit-xml=junit-all.xml

.PHONY: test-cov
test-cov:
	docker compose -f compose.yaml exec -T api uv run python -m pytest --cov=./ --cov-report=term-missing

.PHONY: test-system
test-system:
	@echo "Starting services for system tests..."
	docker compose -f compose.yaml -f compose.system.yaml up -d --build
	@echo "Waiting for backend health at http://api:8000/health..."
	@MAX_RETRIES=45; COUNT=0; \
	until docker compose -f compose.yaml -f compose.system.yaml exec -T api uv run python -c "import urllib.request; urllib.request.urlopen('http://api:8000/health', timeout=5)"; do \
		printf '.'; \
		sleep 2; \
		COUNT=$$((COUNT+1)); \
		if [ $$COUNT -ge $$MAX_RETRIES ]; then \
			echo ""; \
			echo "Backend did not become healthy in time."; \
			docker compose -f compose.yaml -f compose.system.yaml logs api; \
			docker compose -f compose.yaml -f compose.system.yaml logs frontend; \
			exit 1; \
		fi; \
	done
	@echo ""
	@echo "Waiting for frontend readiness at http://frontend:3000..."
	@MAX_RETRIES=45; COUNT=0; \
	until docker compose -f compose.yaml -f compose.system.yaml exec -T api uv run python -c "import urllib.request; urllib.request.urlopen('http://frontend:3000', timeout=5)"; do \
		printf '.'; \
		sleep 2; \
		COUNT=$$((COUNT+1)); \
		if [ $$COUNT -ge $$MAX_RETRIES ]; then \
			echo ""; \
			echo "Frontend did not become ready in time."; \
			docker compose -f compose.yaml -f compose.system.yaml logs frontend; \
			docker compose -f compose.yaml -f compose.system.yaml logs api; \
			exit 1; \
		fi; \
	done
	@echo ""
	@echo "Installing Playwright browsers..."
	docker compose -f compose.yaml -f compose.system.yaml exec -T api uv run playwright install --with-deps chromium
	docker compose -f compose.yaml -f compose.system.yaml exec -T api env BACKEND_URL=http://api:8000 FRONTEND_URL=http://frontend:3000 uv run python -m pytest tests/system/test_stack_mapping.py -v -m system --no-cov
	@echo "System tests complete. Services still running. Use 'make clean' to stop."

# Cleanup targets (Docker-focused)
.PHONY: clean
clean:
	docker compose down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -type d -name node_modules -exec rm -rf {} +
	find . -type d -name .svelte-kit -exec rm -rf {} +
	find . -type d -name dist -exec rm -rf {} +
	find . -type d -name build -exec rm -rf {} +


# Utility targets (Docker-based)
.PHONY: shell
shell:
	docker compose -f compose.yaml exec api uv run python

.PHONY: check-health
check-health:
	curl -s http://localhost:8000/health | python -m json.tool
