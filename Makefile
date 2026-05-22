# ============================================================
# AeroTrack Monorepo - Makefile
# ============================================================

.PHONY: help dev dev-build up down logs backend-shell frontend-shell migrate createsuperuser test lint clean

# Default
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ========================
# Docker Compose
# ========================
dev: ## Start all services in development mode
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

dev-build: ## Build and start all services in development mode
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

up: ## Start all services in production mode
	docker compose up -d

down: ## Stop all services
	docker compose down

down-v: ## Stop all services and remove volumes
	docker compose down -v

logs: ## Tail logs for all services
	docker compose logs -f

logs-backend: ## Tail backend logs
	docker compose logs -f backend

logs-frontend: ## Tail frontend logs
	docker compose logs -f frontend

# ========================
# Shell Access
# ========================
backend-shell: ## Open a shell in the backend container
	docker compose exec backend bash

frontend-shell: ## Open a shell in the frontend container
	docker compose exec frontend sh

db-shell: ## Open psql in the database container
	docker compose exec db psql -U postgres -d aerotrack

redis-cli: ## Open redis-cli
	docker compose exec redis redis-cli

# ========================
# Django Management
# ========================
migrate: ## Run Django migrations
	docker compose exec backend python manage.py migrate

makemigrations: ## Create Django migrations
	docker compose exec backend python manage.py makemigrations

createsuperuser: ## Create Django superuser
	docker compose exec backend python manage.py createsuperuser

collectstatic: ## Collect static files
	docker compose exec backend python manage.py collectstatic --noinput

# ========================
# Testing
# ========================
test: ## Run all tests
	docker compose exec backend python manage.py test
	docker compose exec frontend pnpm test

test-backend: ## Run backend tests only
	docker compose exec backend python manage.py test

test-frontend: ## Run frontend tests only
	docker compose exec frontend pnpm test

# ========================
# Linting
# ========================
lint: ## Run linters
	docker compose exec backend flake8 .
	docker compose exec frontend pnpm lint

lint-backend: ## Lint backend only
	docker compose exec backend flake8 .

lint-frontend: ## Lint frontend only
	docker compose exec frontend pnpm lint

# ========================
# Local Development (without Docker)
# ========================
local-backend: ## Run backend locally (requires venv activated)
	cd backend && source venv/bin/activate && python manage.py runserver

local-frontend: ## Run frontend locally
	cd frontend && pnpm dev

local-install: ## Install all dependencies locally
	cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
	cd frontend && pnpm install

# ========================
# Cleanup
# ========================
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf frontend/dist
	rm -rf backend/staticfiles
