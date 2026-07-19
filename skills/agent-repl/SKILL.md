---
name: agent-repl
description: Process local Excel workbooks and perform iterative Python or data analysis through the persistent Agent REPL. Use this skill whenever the user asks to inspect, clean, calculate, transform, chart, or produce an Excel/data file, or when a Python task benefits from state across steps—even when the user does not mention REPL, Python, Kernel, or this skill. 用户要求处理 Excel、表格、数据分析或多步骤 Python 任务时应主动使用。
compatibility: Requires the agent-repl executable in PATH and a host sandbox for OS-level isolation.
---

# Agent REPL

Treat the user's request as the interface. Keep Runtime, Kernel, workspace, profile, and session mechanics out of the conversation unless diagnosis requires them.

## Start

Use the Agent's current project directory as the workspace. Do not ask the user to configure a workspace or create `inputs`, `working`, or `outputs` directories.

Use `${CLAUDE_SKILL_DIR}/scripts/agent-repl` as the runner when that substitution is supported; it is installed with the exact Runtime path and does not depend on shell PATH. Otherwise use `agent-repl` from PATH.

On the first use in a task, run `<runner> doctor --json`. If it fails, report the installation problem and do not improvise by launching Jupyter or installing packages.

Choose the target automatically:

- `excel` for `.xlsx`/`.xlsm` input or output.
- `data` for tables, CSV/TSV, DataFrames, aggregation, or charts.
- `py` for other iterative Python work.

Invoke `<runner> <target> --json` and pipe multiline Python through stdin. Omit `@session`: the Agent host/task identity selects the persistent session automatically. Add an explicit session only when the same Agent task genuinely needs two isolated states.

## Files

Accept a workbook located directly in the current project or under `inputs/`. Open it with `excel.open("relative/path.xlsx")`; the Runtime creates and edits a working copy. Never overwrite the source.

Publish durable results under `outputs/`. In-memory variables are convenient working state, not deliverables.

## Work iteratively

Inspect before changing. Reuse the same target across calls so variables, imports, DataFrames, and workbook objects persist. Prefer small, verifiable calls over one large opaque program.

For Excel work:

1. Open the source into `wb` with `excel.open(...)`.
2. Inspect sheets and relevant ranges.
3. Apply targeted values, formulas, and formatting without rebuilding unrelated content.
4. Recalculate when formulas changed.
5. Run `wb.scan_formula_errors()`.
6. Publish with `wb.save_output(...)`.
7. Reopen or read cached values when correctness depends on calculation results.

## Errors and completion

Read the JSON contract. Success is `status: ok`. Failure is `status: error` with a non-zero exit code.

If `EXECUTION_TIMEOUT` says `session_recovered: true`, reduce the work and reuse the session. If false, recreate state from the source because the unresponsive Kernel was destroyed.

Finish by telling the user what changed, what was validated, and where the output file is. Do not expose routine CLI transcripts or implementation details.
