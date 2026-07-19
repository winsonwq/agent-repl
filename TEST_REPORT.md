# Agent REPL 0.2.1 Test Report

**Date:** 2026-07-19
**Result:** PASS
**Automated tests:** 28 passed, 0 failed
**Automated test duration:** 20.234 seconds

## Environment

- macOS 27.0 (Build 26A5368g), Apple Silicon
- Python 3.11.5
- Project test environment: ipykernel 6.29.4, jupyter-client 8.6.2, openpyxl 3.1.5, pandas 2.2.0, numpy 1.26.4
- Clean installation environment independently resolved ipykernel 6.31.0, jupyter-client 8.9.1, pandas 2.3.3, numpy 2.4.6, psutil 7.2.2
- LibreOfficeDev 26.8.0.0.alpha0 used for headless formula calculation

## Functional verification

| Area | Verification | Result |
|---|---|---|
| Persistent Python | Separate CLI calls retained `x`; second call returned `42` | PASS |
| Target-free default | `agent-repl 'code'` reused the task-scoped Python Kernel | PASS |
| Persistent DataFrame | DataFrame created in one call and summed in the next | PASS (`2700`) |
| On-demand libraries | pandas and Excel helpers imported in submitted Python instead of selecting a profile | PASS |
| Legacy compatibility | `data@legacy-shared` and `excel@legacy-shared` shared one Kernel and returned `42` | PASS |
| Automatic workspace | Excel source opened directly from project root without workspace configuration | PASS |
| Excel source safety | Source copied to `working` before edits | PASS |
| Excel write/formula | March revenue `1500`; `D6 = B6-C6` | PASS |
| Formula calculation | LibreOffice cached profit | PASS (`720`) |
| Excel Kernel reuse | Later CLI call reused live `wb` | PASS |
| Formula validation | Independent scan found no Excel error cells | PASS |
| Structured errors | User exception returned `CODE_EXECUTION_ERROR` and exit code 1 | PASS |
| Rich SDK | Semantic paths, artifacts, hashes, Runtime metadata, capabilities, and audit events | PASS |

## Security verification

| Control | Verification | Result |
|---|---|---|
| Environment allowlist | Parent test secret was absent inside Kernel | PASS |
| Timeout recovery | Sleeping execution timed out, received SIGINT, and same Kernel subsequently returned `42` | PASS |
| Protected state | Runtime and connection directories created with owner-only permissions | PASS |
| External state | Default state is workspace-namespaced and outside the user project | PASS |
| Path traversal | SDK rejected `../` escape | PASS |
| Resource parsing | Memory/open-file policy parsed deterministically | PASS |
| Automatic cleanup | Test Kernels stopped and records removed | PASS |
| Token benchmark | Updated target-free commands and 10/100/1,000-row break-even assertions | PASS |
| Roadmap quality | Unique task IDs and Python/JavaScript/TypeScript coverage | PASS |

Process creation-time, command, connection path, and random-token verification also ran on every integration execution and cleanup; all live Kernel checks passed.

## Clean installation verification

The one-command installer was run against a new standalone venv and empty project directory, not the development `.venv`:

```text
Runtime installed: PASS
Claude project Skill installed: PASS
Skill-bundled runner executable without PATH: PASS
doctor ready: PASS
Fresh target-free Kernel execution: PASS (42)
Cleanup: PASS (1 Kernel stopped)
Installer rerun/idempotence: PASS
Installer stdout single JSON object: PASS
```

The same installer was then applied to the real user locations: Runtime at `~/.local/share/agent-repl`, Claude Skill at `~/.claude/skills/agent-repl`, `doctor ready: true`, and a PATH-independent Skill runner execution returned `42` before clean shutdown.

## Retained Excel evidence

`test-results/workspace/outputs/sales_model_updated.xlsx` was independently inspected and rendered:

```text
Sales!A1:D7
Mar:   Revenue 1500, Cost 780, Profit 720
Total: Revenue 3700, Cost 2130, Profit 1570
Formula error matches: 0
```

The rendered preview was visually inspected with no clipping, layout damage, or formatting regression.

## Sandbox image status

The Dockerfile and host enforcement command are included and statically reviewed. Docker CLI is installed locally, but the Docker daemon was not running, so an image build was not executed in this test run. Runtime-level limits and local sandbox diagnostics were tested; the Linux image build should additionally run in CI before publishing an image digest.

## Reproduce

```bash
cd /path/to/agent-repl
./scripts/install.sh --agent claude --scope project --project-dir /path/to/test-project
./scripts/run_tests.sh
```

For cached Excel formula verification, provide `soffice`/`libreoffice` on `PATH` or set `AGENT_REPL_SOFFICE`.

## Security boundary

The Runtime defenses protect control state, credentials, lifecycle, and accidental process confusion. They do not turn arbitrary Python into a sandbox. Production guarantees require the documented non-root OS/container boundary, read-only source mounts, network policy, resource quotas, and task-scoped teardown.
