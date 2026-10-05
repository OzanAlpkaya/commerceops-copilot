.DEFAULT_GOAL := help
.PHONY: help up down reset ps logs psql lint format typecheck test check seed ingest

-include .env
POSTGRES_USER ?= commerceops
POSTGRES_DB ?= copilot

COMPOSE := docker compose

help: ## Show available commands
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(firstword $(MAKEFILE_LIST)) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

up: ## Start services and wait until healthy
	$(COMPOSE) up -d --wait

down: ## Stop services
	$(COMPOSE) down

reset: ## Stop services and DELETE the database volume
	$(COMPOSE) down -v

ps: ## Show service status
	$(COMPOSE) ps

logs: ## Follow service logs
	$(COMPOSE) logs -f

psql: ## Open psql in the copilot database
	$(COMPOSE) exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

lint: ## Run ruff lint and format check
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-fix lint issues and format code
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Run pyright
	uv run pyright

test: ## Run tests
	uv run pytest

check: lint typecheck test ## Run all checks (same as CI)

seed: ## Load sample data into the mock customer database (Day 2)
	@echo "Not implemented yet"

ingest: ## Ingest the document corpus (Day 4)
	@echo "Not implemented yet"
