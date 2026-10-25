.DEFAULT_GOAL := help

PRE_COMMIT_VERSION ?= 4.7
PRE_COMMIT ?= uvx pre-commit@$(PRE_COMMIT_VERSION)

help:           ## list targets
	@grep -E '^[a-z.-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "%-12s %s\n", $$1, $$2}'

install:        ## install ewsctl into PATH (editable, via uv tool)
	uv tool install --editable --force .

sync:           ## create/refresh the dev venv
	uv sync --group dev

lint: sync lint.pre-commit  ## ruff check + format check + mypy + pre-commit hooks
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

lint.pre-commit:  ## pre-commit hooks: gitleaks, actionlint, renovate config, whitespace
	$(PRE_COMMIT) run --all-files

fmt: sync       ## autoformat + autofix
	uv run ruff format .
	uv run ruff check --fix .

rules: sync     ## quick smoke test: list server rules
	uv run python ewsctl.py rules list -v

.PHONY: help install sync lint lint.pre-commit fmt rules
