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
	@echo ""

	@echo "Cleanup (Docker):"
	@echo "  clean         - Stop containers and remove Docker artifacts, Python cache, node modules, and build files"
	@echo ""
	@echo "Utilities (via Docker):"
	@echo "  shell         - Open Python shell in container"
	@echo "  check-health  - Check API health endpoint"
	@echo "  db-health     - Check database health endpoint"

# Development targets (Docker-based)
.PHONY: install
install:
	docker compose -f compose.yaml build && docker compose -f compose.yaml up -d

.PHONY: run
run:
	docker compose -f compose.yaml up --build -d
	docker compose -f compose.yaml exec -T api uv run python -m alembic upgrade head
	docker compose -f compose.yaml logs -f api


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
	docker compose -f compose.yaml exec -T api uv run python -m pytest -m "not integration" -q --junit-xml=junit-unit.xml

.PHONY: test-cov
test-cov:
	docker compose -f compose.yaml exec -T api uv run python -m pytest --cov=./ --cov-report=term-missing

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

.PHONY: db-health
db-health:
	curl -s http://localhost:8000/db-health | python -m json.tool
