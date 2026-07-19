---
name: agent-repl
description: Process local Excel workbooks and perform iterative Python or data analysis through the persistent Agent REPL. Use this skill whenever the user asks to inspect, clean, calculate, transform, chart, or produce an Excel/data file, or when a Python task benefits from state across steps—even when the user does not mention REPL, Python, Kernel, or this skill. 用户要求处理 Excel、表格、数据分析或多步骤 Python 任务时应主动使用。
compatibility: Requires an installed agent-repl Runtime and a host sandbox for OS-level isolation.
---

# Agent REPL

Treat the user's request as the interface. Keep Runtime, Kernel, workspace, and session mechanics out of the conversation unless diagnosis requires them. Use the persistent Python state for iterative work and keep durable results in files.

## Start

Use the current project directory as the workspace. Do not ask the user to configure a workspace or create support directories.

Use `${CLAUDE_SKILL_DIR}/scripts/agent-repl` as the runner when that substitution is supported; it is installed with the exact Runtime path and does not depend on shell PATH. Otherwise use `agent-repl` from PATH.

On first use, run `<runner> doctor --json`. If it fails, report the installation problem; do not launch Jupyter or install packages.

Invoke `<runner> --stdin --json` and pipe Python through stdin. Import pandas, NumPy, `agent_repl_excel`, or other installed libraries when needed. Do not select `py`, `data`, or `excel`: they are deprecated aliases, not capabilities. Omit `--session`; add it only for two intentionally isolated states in one task.

## Files

Accept workbook input from the project root or `inputs/`. Never overwrite the source.

Publish durable results under `outputs/`; memory state is not a deliverable.

## Execute

Inspect before changing. Reuse the default session so variables, imports, DataFrames, and workbook objects persist. Prefer small, verifiable calls.

For Excel work, read [references/excel.md](references/excel.md) and follow its verification workflow.

## Errors and completion

Success is `status: ok`. Failure is `status: error` with a non-zero exit code.

If `EXECUTION_TIMEOUT` says `session_recovered: true`, reduce the work and reuse the session. If false, recreate state from the source because the unresponsive Kernel was destroyed.

Finish with what changed, what was validated, and the output path. Hide routine CLI transcripts.
