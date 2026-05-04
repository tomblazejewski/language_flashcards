.PHONY: help dev test lint typecheck migrate migrate-create migrate-down docker-up docker-down seed

PYTHON := uv run python
PYTEST := uv run pytest
RUFF   := uv run ruff
TY     := uv run ty
ALEMBIC := uv run --directory backend alembic

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ------------------------------------------------------------------ #
# Development server
# ------------------------------------------------------------------ #

dev:  ## Run the backend dev server with auto-reload (SQLite)
	cp -n .env.example .env 2>/dev/null || true
	uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000 \
		--app-dir backend

dev-pg:  ## Run the backend dev server against the Docker PostgreSQL instance
	DATABASE_URL=postgresql+asyncpg://flashcards:flashcards@localhost:5432/flashcards \
	uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000 \
		--app-dir backend

# ------------------------------------------------------------------ #
# Testing
# ------------------------------------------------------------------ #

test:  ## Run the test suite
	$(PYTEST) --cov --cov-report=term-missing -v

test-fast:  ## Run tests without coverage (faster)
	$(PYTEST) -v

# ------------------------------------------------------------------ #
# Code quality
# ------------------------------------------------------------------ #

lint:  ## Run ruff linter and auto-fix safe issues
	$(RUFF) check backend --fix
	$(RUFF) format backend

lint-check:  ## Check linting without modifying files (for CI)
	$(RUFF) check backend
	$(RUFF) format backend --check

typecheck:  ## Run ty type checking
	$(TY) check backend/app

# ------------------------------------------------------------------ #
# Database migrations
# ------------------------------------------------------------------ #

migrate:  ## Apply all pending Alembic migrations
	$(ALEMBIC) upgrade head

migrate-create:  ## Create a new migration (usage: make migrate-create MSG="your message")
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

migrate-down:  ## Roll back the last migration
	$(ALEMBIC) downgrade -1

migrate-history:  ## Show migration history
	$(ALEMBIC) history --verbose

# ------------------------------------------------------------------ #
# Docker
# ------------------------------------------------------------------ #

docker-up:  ## Start PostgreSQL and backend via docker-compose
	docker compose up -d

docker-down:  ## Stop docker-compose services
	docker compose down

docker-logs:  ## Tail docker-compose logs
	docker compose logs -f

# ------------------------------------------------------------------ #
# Utilities
# ------------------------------------------------------------------ #

seed:  ## Run the development seed script
	$(PYTHON) backend/scripts/seed.py

clean:  ## Remove Python cache files and test artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage htmlcov .mypy_cache .pytest_cache dev.db
