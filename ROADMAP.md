# Agent REPL Roadmap

**Version:** 1.0.1
**Status:** Proposed
**Scope:** Keep Python as the production runtime and preserve a clean path to optional JavaScript, TypeScript, and later adapters.

## Current constraint

Version 0.2.1 intentionally exposes one target-free Python entry. pandas and Excel are libraries loaded on demand, not runtime profiles. Four implementation points remain Python-specific:

| Area | Current coupling | Required abstraction |
|---|---|---|
| Process start | `python -m ipykernel_launcher` | Runtime Adapter `start()` |
| Transport | Jupyter connection file/client | Adapter-owned endpoint and transport |
| Execution | Jupyter IOPub and shell messages | Common execution event envelope |
| Identity/interrupt | Command must contain `ipykernel_launcher` | Adapter-owned `verify()` and `interrupt()` |

Adding `js` and `ts` as aliases would be misleading because they would still start Python. Adapter extraction is therefore the first dependency. Runtime selection may return later only when more than one real execution engine ships.

## Target architecture

```text
agent-repl CLI / Skill / JSON contract
              |
       RuntimeAdapter registry
       /          |           \
PythonJupyter  NodeWorker   Future adapters
                   |
            JavaScript context
                   |
          TypeScript transpiler
```

Every adapter implements the same lifecycle:

```text
start -> verify -> execute -> interrupt -> health -> terminate
```

Adapters may use different transports, but return the same `stdout`, `stderr`, `result`, `display`, `artifact`, `error`, timeout, and session metadata events.

## Language priority

| Runtime | User value | Proposed engine | Priority | Notes |
|---|---|---|---|---|
| Python | Data, automation, Excel | Jupyter/ipykernel | Shipped | Becomes the reference adapter |
| JavaScript | Node projects, JSON, web tooling | Persistent Node child + IPC | P1 | Broad npm compatibility |
| TypeScript | Typed project analysis and generation | TS transpile layer over Node worker | P1 | Optional incremental type check |
| SQL | Stateful analytical queries | DuckDB connection/profile | P2 | Likely hosted inside Python first |
| Deno JS/TS | Permission-oriented alternative | Deno process adapter | P3 experimental | Do not use Deno Jupyter as a secure default while it runs `--allow-all` |
| R | Statistical analysis | IRkernel/Jupyter adapter | P3 | Reuses Jupyter transport |
| Java/Kotlin | JVM project exploration | JShell/Kotlin adapter | Backlog | Higher startup and packaging cost |
| Shell | Stateful shell | None by default | Rejected initially | Persistent shell expands security risk with little state benefit |

## Milestone 0 — v0.2.1: shrink and stabilize the control plane

- [ ] **AR-101 — Introduce `RuntimeAdapter` protocol** (L)
  - Define start, endpoint, execute, verify, interrupt, health, and terminate methods.
  - Acceptance: `sessions.py` contains no `ipykernel_launcher` or Jupyter imports.
- [ ] **AR-102 — Move Python into `PythonJupyterAdapter`** (M; depends on AR-101)
  - Preserve all current JSON events and regression tests.
  - Acceptance: the target-free CLI remains primary; `py`, `data`, and `excel` remain compatibility aliases to the same Kernel.
- [ ] **AR-103 — Version the session record schema** (M; depends on AR-101)
  - Add adapter kind, endpoint descriptor, schema version, and migration path.
  - Acceptance: v0.2 records either migrate safely or fail without signaling a process.
- [ ] **AR-104 — Define runtime manifests only for material isolation** (M)
  - Describe executable, dependencies, adapter, permissions, and resource policy; never create a profile solely for imports.
  - Acceptance: `doctor` validates every shipped runtime manifest and no domain library creates a separate session identity.
- [ ] **AR-105 — Define the cross-language event contract** (M)
  - Specify result serialization, rich MIME artifacts, stack traces, async completion, and truncation.
  - Acceptance: contract tests run against a fake adapter and Python adapter.
- [ ] **AR-106 — Split Skill guidance by progressive disclosure** (S)
  - Keep routing/common rules in `SKILL.md`; move Excel, data, JS, and TS details into references.
  - Current: Excel guidance moved to a lazy reference and the main Skill fell from 677 to 526 `cl100k_base` tokens.
  - Acceptance: main Skill reaches at most 300 tokens without losing trigger coverage.

## Milestone 1 — v0.3.0: JavaScript Runtime

- [ ] **AR-201 — Implement persistent Node worker** (L; depends on AR-101/105)
  - Launch a detached Node child with sanitized environment and private IPC endpoint.
  - Prefer direct child IPC/Unix socket or Windows named pipe; never pass code through shell quoting.
- [ ] **AR-202 — Define JavaScript cell semantics** (L)
  - Support top-level await, persistent bindings, Promise results, console capture, and structured errors.
  - Decide and test redeclaration, ESM import caching, CommonJS compatibility, and unhandled rejections.
- [ ] **AR-203 — Add JavaScript `ctx` SDK** (M)
  - Match semantic paths, publishing, SHA-256 metadata, capabilities, and audit events.
- [ ] **AR-204 — Generalize process identity** (M)
  - Node adapter verifies PID, creation time, command, endpoint, and random token before signaling.
- [ ] **AR-205 — Apply timeout and resource policy** (M)
  - Interrupt cooperative execution; destroy an unresponsive Node process group.
  - Optionally enable Node permission flags as defense in depth, never as the sole sandbox.
- [ ] **AR-206 — Ship `js` runtime selection and E2E tests** (M)
  - Acceptance: an explicit JavaScript runtime selection preserves `let x = 41` and returns `42` across CLI processes without changing Python's default grammar.

Node's official documentation says `node:vm` is not a security mechanism. The Node worker therefore remains inside the same required OS/container sandbox as Python. Process IPC is appropriate for lifecycle and serialization, not isolation: [Node VM](https://nodejs.org/api/vm.html), [Node child process/IPC](https://nodejs.org/api/child_process.html), [Node permission model](https://nodejs.org/api/permissions.html).

## Milestone 2 — v0.4.0: TypeScript Runtime

- [ ] **AR-301 — Add TypeScript transpilation pipeline** (L; depends on AR-201/202)
  - Start with the official TypeScript compiler API and source maps.
  - Keep transpilation separate from optional type checking.
- [ ] **AR-302 — Preserve TypeScript cell state** (L)
  - Define how erased types, top-level bindings, imports, declarations, and redeclarations behave across cells.
- [ ] **AR-303 — Add incremental project type checking** (M)
  - Provide `transpile-only` for fast REPL calls and `check` for explicit validation.
  - Return diagnostics in the common error envelope with file/line mappings.
- [ ] **AR-304 — Respect project configuration** (M)
  - Discover `tsconfig.json`, package type, path aliases, module resolution, and lockfiles without mutating them.
- [ ] **AR-305 — Ship `ts` runtime selection and E2E tests** (M)
  - Acceptance: typed bindings persist, source-mapped runtime errors point to TypeScript, and check mode reports deterministic diagnostics.

The TypeScript compiler exposes `transpileModule`, but module semantics still require deliberate configuration and tests: [TypeScript modules](https://www.typescriptlang.org/docs/handbook/modules), [transpileModule reference](https://www.typescriptlang.org/docs/handbook/release-notes/typescript-5-5.html).

## Milestone 3 — v0.5.0: optional adapters and modular distribution

- [ ] **AR-401 — SQL/DuckDB adapter or Python library integration** (M)
  - Persist connection/catalog state while publishing large results as files rather than model JSON.
- [ ] **AR-402 — Evaluate Deno adapter** (M)
  - Compare a permission-scoped Deno process adapter with its built-in Jupyter kernel.
  - Block production default while the official Jupyter mode runs with `--allow-all`: [Deno Jupyter](https://docs.deno.com/runtime/reference/cli/jupyter/).
- [ ] **AR-403 — R/IRkernel spike** (M)
  - Reuse a generic Jupyter adapter if event compatibility passes.
- [ ] **AR-404 — Modular installer** (L)
  - Support `--runtime python`, `--runtime node`, and `--runtime all` with immutable version manifests.
- [ ] **AR-405 — Multi-architecture sandbox images** (L)
  - Publish pinned amd64/arm64 images, SBOM, dependency hashes, and vulnerability scan evidence.

## Cross-cutting security TODO

- [ ] **SEC-101:** one adapter-specific process verifier per runtime; never signal using PID alone.
- [ ] **SEC-102:** endpoint directories/sockets remain owner-only and outside user workspaces.
- [ ] **SEC-103:** environment allowlist is common; adapter-specific variables are explicit.
- [ ] **SEC-104:** package installation is disabled inside production sessions; images/manifests pin dependencies.
- [ ] **SEC-105:** network, read-only inputs, UID, CPU, memory, PIDs, and teardown stay host-enforced.
- [ ] **SEC-106:** add adversarial tests for endpoint tampering, PID reuse, fork bombs, runaway async work, and secret access.
- [ ] **SEC-107:** define artifact size/count quotas and audit-log redaction.

## Token and performance TODO

- [ ] **PERF-101:** run `benchmarks/token_cost.py` in CI and fail on unexpected Skill/context growth.
- [ ] **PERF-102:** measure real Agent traces for one-shot, iterative, and cross-domain tasks; do not treat tokenizer estimates as billing data.
- [ ] **PERF-103:** compare shared memory, artifact-path handoff, Arrow/Parquet handoff, and model-mediated JSON.
- [ ] **PERF-104:** record Kernel cold start, warm call p50/p95, RSS, and interrupt recovery per adapter.
- [ ] **PERF-105:** keep result previews bounded and publish large values as artifacts.

## Definition of done for every runtime

- Python keeps the shortest grammar: `agent-repl [code]`; additional runtimes require explicit selection.
- Same success/error JSON envelope and exit-code classes.
- State persists across separate CLI processes and is isolated by workspace/task/optional session; a runtime dimension is added only when multiple engines ship.
- Source files remain unchanged; durable results publish with hashes.
- Environment secrets do not enter the runtime unless explicitly allowlisted.
- Timeout recovery and forced termination are tested.
- Process identity is verified before every signal.
- `doctor`, install, clean, and stale-session collection work.
- Functional, security, token, cold-start, and memory evidence is recorded.

## Success criteria

| Goal | Target |
|---|---:|
| Main Skill routing context | ≤300 `cl100k_base` tokens |
| Warm local execution overhead excluding user code | p95 ≤150 ms |
| Cross-CLI state persistence | 100% contract-test pass rate |
| Unverified process signals | 0 |
| Parent secret leakage | 0 default-denied variables |
| Adapter contract parity | Python, JS, and TS all pass the same event/lifecycle suite |
| Large tabular model handoff | Default to artifact/shared state above configurable preview limit |

## Changelog

- **1.0.1 (2026-07-19):** make Python target-free, treat data/Excel as on-demand libraries, and reserve profiles for material runtime isolation.
- **1.0.0 (2026-07-19):** initial multi-language adapter plan, security backlog, token goals, and acceptance criteria.
