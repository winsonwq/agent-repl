# Agent REPL 0.2 Architecture

## Interaction model

```text
User: "处理 report.xlsx，修正公式并输出新文件"
  |
  v
Agent Skill
  |-- chooses excel/data/py
  |-- current directory = workspace
  |-- host identity = session identity
  |-- invokes bundled Runtime runner
  v
Short-lived agent-repl CLI
  |-- protected state registry outside workspace
  |-- cross-process lock
  |-- verifies or starts Kernel
  v
Long-lived ipykernel
  |-- ctx generic SDK
  |-- optional Excel/data SDK
  |-- retained variables and objects
  v
source -> working copy -> outputs/artifacts
```

The user never needs to know the Runtime profile, Kernel name, session name, state path, or workspace environment variable.

## Identity and routing

The state root is outside the project and is namespaced by the resolved workspace path. Session identity prefers a host-injected `AGENT_TASK_ID`, Claude/Codex session ID, or a detected local Agent host process. A plain terminal falls back to `default` inside the workspace namespace.

The routing key remains conceptually:

```text
workspace namespace + task identity + runtime profile + optional logical session
```

Consequently, `agent-repl excel` is normally enough. Explicit `excel@scenario-b` is reserved for genuine parallel state inside one Agent task.

## Runtime security controls

### Protected control state

State directories use mode `0700`; records, contexts, connection secrets, and locks use `0600`. Stored paths must resolve to the Runtime-owned directories.

### Process identity

Each Kernel record stores its PID, OS process creation time, connection path, and a 256-bit random process token passed through the sanitized Kernel environment. Before reconnecting or sending a process-group signal, the Runtime verifies all identity attributes and the expected ipykernel command. A stale or tampered PID is never signaled.

### Environment

Kernels receive a small operational allowlist such as `PATH`, locale, temporary/home locations, certificate paths, and the configured LibreOffice path. Parent credentials are not copied. Administrators may explicitly add non-secret variables with `AGENT_REPL_ENV_ALLOWLIST`.

### Timeout and lifecycle

On execution timeout the Runtime signals only the verified Kernel process group, waits for Jupyter responsiveness, and returns whether the session recovered. An unresponsive Kernel is terminated and its control record removed. Idle Kernel collection is available through `gc` and runs opportunistically with a configurable TTL.

### Resource policy

On POSIX hosts, optional rlimits cover memory address space, cumulative CPU, output file size, open files, and child processes. The deployment image configures these as defense in depth. Container or OS controls remain authoritative.

## OS sandbox boundary

No Python library can safely prevent arbitrary Python from bypassing another Python library. Therefore production isolation is a composition:

```text
Agent REPL controls
  + one task per non-root sandbox
  + read-only source mount
  + writable working/output mounts
  + network policy
  + CPU/memory/PID quotas
  + secret-free process environment
  + sandbox destruction at task completion
```

`agent-repl doctor` reports `ready` for local functional readiness and a separate `production_ready` flag requiring declared host sandbox enforcement and resource policy.

The direct Jupyter connection remains appropriate for one Agent inside one OS sandbox. A shared multi-user service still requires a privileged supervisor/daemon that owns authorization, connection secrets, quotas, and lifecycle across sandboxes.
