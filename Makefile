.PHONY: setup setup-backend setup-frontend dev dev-backend dev-frontend test test-backend test-frontend lint lint-backend lint-frontend migrate docker-up docker-down clean

# =============================================================================
# Setup
# =============================================================================

setup: setup-backend setup-frontend ## Install all dependencies

setup-backend: ## Install backend dependencies
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

setup-frontend: ## Install frontend dependencies
	cd frontend && npm install

# =============================================================================
# Development
# =============================================================================

dev: ## Run both backend and frontend (requires two terminals or use docker-up)
	@echo "Run 'make dev-backend' and 'make dev-frontend' in separate terminals."
	@echo "Or use 'make docker-up' to start everything with Docker Compose."

dev-backend: ## Run the backend with hot reload
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Run the frontend dev server
	cd frontend && npm run dev

# =============================================================================
# Testing
# =============================================================================

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	cd backend && . .venv/bin/activate && pytest

test-frontend: ## Run frontend tests
	cd frontend && npm test -- --run

# =============================================================================
# Linting and type checking
# =============================================================================

lint: lint-backend lint-frontend ## Lint and type-check everything

lint-backend: ## Lint and type-check backend
	cd backend && . .venv/bin/activate && ruff check . && ruff format --check . && mypy app/ --ignore-missing-imports

lint-frontend: ## Lint and type-check frontend
	cd frontend && npm run lint && npm run type-check

# =============================================================================
# Database
# =============================================================================

migrate: ## Run Alembic migrations to head
	cd backend && . .venv/bin/activate && alembic upgrade head

migrate-generate: ## Generate a new migration (usage: make migrate-generate MSG="add foo table")
	cd backend && . .venv/bin/activate && alembic revision --autogenerate -m "$(MSG)"

migrate-rollback: ## Roll back one migration
	cd backend && . .venv/bin/activate && alembic downgrade -1

migrate-history: ## Show migration history
	cd backend && . .venv/bin/activate && alembic history --verbose

# =============================================================================
# Docker
# =============================================================================

docker-up: ## Start all services with Docker Compose
	docker compose up -d

docker-down: ## Stop all services
	docker compose down

docker-logs: ## Follow logs from all services
	docker compose logs -f

docker-reset: ## Stop services and remove volumes (destructive)
	docker compose down -v

# =============================================================================
# Cleanup
# =============================================================================

clean: ## Remove build artifacts and caches
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist frontend/.vite 2>/dev/null || true

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
