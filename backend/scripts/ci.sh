#!/usr/bin/env bash
# Full backend check suite. Order matters: format, lint, types, then tests.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== format =="
uv run ruff format --check .

echo "== lint =="
uv run ruff check .

echo "== types =="
uv run mypy

echo "== tests + coverage =="
uv run pytest --cov --cov-report=term

echo "All checks passed."
