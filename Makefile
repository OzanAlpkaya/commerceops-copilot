.DEFAULT_GOAL := help
.PHONY: help up down reset ps logs psql psql-commerce lint format typecheck test check seed ingest

-include .env
POSTGRES_USER ?= commerceops
POSTGRES_PASSWORD ?= commerceops
POSTGRES_DB ?= copilot
# Host-side connections follow .env; the fallbacks mirror docker-compose.yml.
POSTGRES_HOST ?= localhost
POSTGRES_PORT ?= 5432
COMMERCE_DB := lumora_commerce
COMMERCE_DATABASE_URL := postgresql+psycopg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@$(POSTGRES_HOST):$(POSTGRES_PORT)/$(COMMERCE_DB)

COMPOSE := docker compose

help: ## Show available commands
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(firstword $(MAKEFILE_LIST)) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

up: ## Build and start services, wait until healthy
	$(COMPOSE) up -d --wait --build

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

psql-commerce: ## Open psql in the mock order system database
	$(COMPOSE) exec db psql -U $(POSTGRES_USER) -d $(COMMERCE_DB)

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

seed: ## Reset the mock order database to the Olist-based seed data
	@MOCK_API_DATABASE_URL=$(COMMERCE_DATABASE_URL) uv run --package mock-api python -m mock_api.seed

ingest: ## Ingest the document corpus (Day 4)
	@echo "Not implemented yet"
