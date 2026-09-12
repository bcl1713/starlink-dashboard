#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."
exec uv run --with-requirements requirements.txt \
  pytest tests/unit/test_config.py "$@"
