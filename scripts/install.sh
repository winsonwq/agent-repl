#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec "${PYTHON_BIN:-python3}" "$PROJECT_DIR/scripts/install.py" "$@"
