# Agent REPL 0.2.1

Agent REPL gives a shell-capable Agent a persistent Python runtime. Short-lived CLI calls reconnect to one long-lived Jupyter Kernel, preserving variables, imports, DataFrames, and Excel workbook objects across steps.

The user-facing interface is the Agent Skill: users describe the task and do not configure a workspace, runtime, or session. The current release has one production runtime—Python—and loads pandas, Excel helpers, and other libraries only when the task needs them.

## Install Runtime and Skill

From this repository, install the Runtime and personal Claude Code Skill in one idempotent command:

```bash
./scripts/install.sh --agent claude
```

The installed Skill contains a runner with the exact Runtime path, so Claude Code does not depend on shell `PATH`. Restart Claude Code after the first installation, then work in any project directory.

For a project-only Skill:

```bash
./scripts/install.sh --agent claude --scope project --project-dir /path/to/project
```

Codex is also supported by `--agent codex`; use `--agent both` to install both Skill copies.

## User experience

Start Claude Code in the directory containing the user's files:

```bash
cd /path/to/project
claude
```

Then ask naturally:

```text
帮我处理 report.xlsx，把三月份收入改成 1800，重新计算利润，
检查公式错误并给我一个新文件。
```

The Skill uses the current directory as the workspace, reconnects to the task-scoped Python session, imports the required libraries, preserves the source, and publishes results under `outputs/`.

Excel files may be in the project root or under `inputs/`. No environment variables or directory setup are required.

## Runtime operations

These commands are primarily for the Skill and diagnostics:

```bash
agent-repl doctor --json
agent-repl 'x = 41' --json
agent-repl 'x + 1' --json
agent-repl --session experiment-a --stdin < analyze.py
agent-repl sessions --json
agent-repl status --json
agent-repl stop --json
agent-repl gc --stale-minutes 240 --json
agent-repl clean --json
```

An explicit `--session` remains available when one task needs isolated states, but normal Agent use omits it. `AGENT_TASK_ID`, Claude/Codex session variables, or the detected local Agent process provide the task identity automatically.

The v0.2 forms `py`, `data`, `excel`, and `alias@session` remain accepted as compatibility aliases. They no longer select separate Kernels: all aliases route to the same Python session, while `data` and `excel` only inject their former convenience imports. New integrations should use the target-free form and import libraries explicitly.

## Excel API

The Skill internally follows this pattern:

```python
from agent_repl_excel import excel

wb = excel.open("report.xlsx")
wb.read_range("Sales!A1:D10")
wb.set_value("Sales!B6", 1800)
wb.set_formula("Sales!D6", "=B6-C6")
wb.recalculate()
wb.scan_formula_errors()
wb.save_output("report-updated.xlsx")
```

The source remains unchanged. Editing occurs under `working/`, and the durable result is published under `outputs/` with SHA-256 metadata.

## Security

Version 0.2 adds Runtime-level defenses:

- state stored outside the user workspace in an owner-only, workspace-namespaced runtime directory;
- connection and session files restricted to the owner;
- Kernel process identity verified by PID, creation time, command, connection path, and random token before execution or termination;
- Kernel environment built from an allowlist instead of inheriting credentials and Tokens;
- execution timeouts send an interrupt, verify recovery, and destroy an unresponsive Kernel;
- optional POSIX memory, CPU, file-size, open-file, and process limits;
- automatic stale-session collection;
- `doctor` reports local readiness separately from production sandbox readiness.

Python remains arbitrary code. Filesystem mounts, network denial, container resources, user identity, and sandbox teardown must be enforced by the Agent host. See [deploy/README.md](deploy/README.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

## Sandbox image

`deploy/Dockerfile` preinstalls the Runtime, Excel dependencies, LibreOffice, a non-root user, and Runtime resource policies. The example launch command adds `--network none`, container memory/CPU/PID limits, a read-only root filesystem, and tmpfs runtime state.

## Verify

```bash
./scripts/run_tests.sh
```

See [TEST_REPORT.md](TEST_REPORT.md) for the local functional, security, installation, and Excel verification results.

Planning and architecture evaluation:

- [ROADMAP.md](ROADMAP.md) — prioritized Python/JavaScript/TypeScript and future-runtime TODOs.
- [CLI_COMPARISON.md](CLI_COMPARISON.md) — unified vs. scattered CLI evaluation with reproducible token data.
- [benchmarks/results/token-cost.md](benchmarks/results/token-cost.md) — generated benchmark table.

## Repository layout

```text
src/agent_repl/         CLI, security, sessions and Jupyter execution
src/agent_repl_sdk/     generic in-Kernel SDK
src/agent_repl_excel/   Excel domain runtime
skills/agent-repl/      natural-language Agent Skill, runner and eval cases
scripts/install.*       one-command idempotent installer
deploy/                 sandbox image and host-enforcement example
tests/                  unit, security and end-to-end tests
benchmarks/             reproducible Agent context/token estimates
```
