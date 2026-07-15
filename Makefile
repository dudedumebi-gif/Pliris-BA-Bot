.PHONY: install lock verify-env check-supabase test test-integration lint format api

install:
	uv sync --all-extras

lock:
	uv lock

verify-env:
	uv run python -m scripts.verify_environment

check-supabase:
	uv run python -m scripts.check_supabase

test:
	uv run pytest -m "not integration"

test-integration:
	uv run pytest -m integration

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

api:
	uv run fastapi dev api/main.py
