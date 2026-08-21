.DEFAULT_GOAL := help

help:           ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "%-12s %s\n", $$1, $$2}'

install:        ## install ewsctl into PATH (editable, via uv tool)
	uv tool install --editable --force .

sync:           ## create/refresh the dev venv
	uv sync --group dev

lint: sync      ## ruff check + format check + mypy
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

fmt: sync       ## autoformat + autofix
	uv run ruff format .
	uv run ruff check --fix .

rules: sync     ## quick smoke test: list server rules
	uv run python ewsctl.py rules list -v

.PHONY: help install sync lint fmt rules
