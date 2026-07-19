#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

cd "$PROJECT_DIR"
"$PYTHON_BIN" -c 'import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)' "$PROJECT_DIR/test-results"
mkdir -p test-results/workspace/inputs
cp tests/fixtures/sales_model.xlsx test-results/workspace/inputs/sales_model.xlsx

export AGENT_REPL_SOFFICE="${AGENT_REPL_SOFFICE:-$(command -v soffice || command -v libreoffice || true)}"

"$PYTHON_BIN" -m unittest discover -s tests -v 2>&1 | tee test-results/unittest.log

# Produce a deterministic, retained Excel E2E result for visual QA.
export AGENT_TASK_ID="retained-e2e"
export AGENT_REPL_STATE_DIR="$PROJECT_DIR/test-results/state"
export AGENT_REPL_WORKDIR="$PROJECT_DIR/test-results/workspace"
export AGENT_REPL_OUTPUT=json

"$PYTHON_BIN" -m agent_repl.cli excel@finance --json <<'PY' | tee test-results/excel-e2e.json
wb = excel.open_input('sales_model.xlsx')
wb.set_value('Sales!B6', 1500)
wb.set_formula('Sales!D6', '=B6-C6')
calculation = wb.recalculate()
errors = wb.scan_formula_errors()
output = wb.save_output('sales_model_updated.xlsx', title='Updated sales model')
{'calculation': calculation, 'errors': errors, 'output': output, 'cached_profit': wb.cached_value('Sales!D6')}
PY

"$PYTHON_BIN" -m agent_repl.cli clean --json >/dev/null

echo "Tests and retained Excel output completed."
