.DEFAULT_GOAL := help
.PHONY: help install up down logs test lint format typecheck check

POETRY ?= poetry

help:
	@echo "install    установка зависимостей"
	@echo "up         поднять окружение в docker"
	@echo "down       остановить окружение и удалить тома"
	@echo "logs       логи consumer и outbox"
	@echo "test       pytest"
	@echo "lint       ruff check"
	@echo "format     ruff format"
	@echo "typecheck  mypy"
	@echo "check      lint + typecheck + test"

install:
	$(POETRY) install

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f consumer outbox

test:
	$(POETRY) run pytest -q

lint:
	$(POETRY) run ruff check src cli tests migrations

format:
	$(POETRY) run ruff format src cli tests migrations

typecheck:
	$(POETRY) run mypy src cli

check: lint typecheck test
