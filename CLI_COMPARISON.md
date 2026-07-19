# Unified Agent REPL vs. Scattered CLIs

## Executive assessment

The strongest reason for one `agent-repl` control plane is not that a single command is always shorter. Its real advantage is shared state plus one lifecycle, security, artifact, error, and observability contract across runtimes.

Token usage has a boundary:

- A small one-shot domain task can be cheaper with a narrowly documented CLI.
- A multi-step workflow becomes cheaper with Agent REPL when otherwise the model must carry meaningful state or data between commands.
- Well-designed scattered CLIs that hand off artifact paths instead of data can approach or beat Agent REPL's token cost, but still duplicate lifecycle and policy unless they share a control plane—in effect recreating this architecture.

The recommended design is therefore hybrid: one user-facing CLI and Skill, with separate internal Runtime Adapters and domain packages.

## Compared designs

| Unified control plane | Scattered CLI suite |
|---|---|
| `agent-repl py`, `js`, `ts`, `excel` | `python-repl`, `javascript-repl`, `typescript-repl`, `excel-cli`, `dataframe-cli`, `artifact-cli`, `session-cli` |
| One Skill/router | Separate discovery metadata and help for each CLI |
| One session key and state registry | Each CLI defines or delegates its own state |
| One JSON event/error contract | Command-specific schemas unless separately standardized |
| Runtime Adapters behind the CLI | Independent executables are the public integration surface |

## Reproducible token estimates

The checked-in benchmark uses `tiktoken cl100k_base`. This is a reproducible relative context estimate, not Claude/OpenAI billing data; model tokenizers differ. Run:

```bash
python benchmarks/token_cost.py
```

### Context and workflow cost

| Metric | Unified tokens | Scattered tokens | Unified change | Interpretation |
|---|---:|---:|---:|---|
| Always-visible discovery metadata | 126 | 138 | −8.7% | Small catalog advantage; only 12 tokens per context load |
| All capability guidance loaded | 677 | 461 | +46.9% | Current unified Skill is too broad and needs progressive disclosure |
| Four-step Excel commands only | 112 | 148 | −24.3% | Shared object/session grammar removes repeated paths and flags |
| Four-step Excel, guidance + commands | 789 | 344 | +129.4% | Narrow Excel docs win for a small one-domain task |
| Excel→DataFrame with artifact paths | 786 | 367 | +114.2% | A disciplined artifact protocol prevents data-token costs |
| Mixed workflow, 10-row JSON handoff | 786 | 745 | +5.5% | Near break-even; unified Skill overhead is still visible |
| Mixed workflow, 100-row JSON handoff | 786 | 4,318 | −81.8% | Persistent state avoids 3,965 JSON tokens |
| Mixed workflow, 1,000-row JSON handoff | 786 | 40,318 | −98.1% | Model-mediated data transfer dominates everything else |

Negative cost is not automatic. The present main Skill is 677 tokens, while the seven deliberately minimal scattered help texts total 461. `ROADMAP.md` therefore makes splitting the main Skill to at most 300 tokens a P0 item.

### Data handoff alone

| Rows × columns | JSON through model | Artifact reference | Shared state avoids |
|---:|---:|---:|---:|
| 10 × 8 | 392 | 23 | 392 |
| 100 × 8 | 3,965 | 23 | 3,965 |
| 1,000 × 8 | 39,965 | 23 | 39,965 |

The break-even in this fixture is roughly a dozen rows. This is not a universal row threshold: long strings, nested values, language, and model tokenizer change it. The architectural rule should be based on measured preview tokens/bytes, not row count alone.

### Measurement limits

| Not measured | Effect |
|---|---|
| Provider-specific tokenizer | Absolute counts and break-even can move |
| Prompt/context caching | Repeated static guidance may be cheaper in billed input than raw token count suggests |
| Model reasoning and retries | Ambiguous CLI selection or inconsistent errors can add much more than command text |
| Tool output previews | Verbose results can dominate either architecture |
| Runtime latency/CPU/RSS | Token efficiency does not imply faster execution or a smaller image |

The fixture and every command string are checked into `benchmarks/token_cost.py`, so assumptions are inspectable rather than hidden inside the table.

## Engineering scorecard

The following is a documented engineering judgment, not a benchmark. Scores are 1–5 and weights total 100.

| Criterion | Weight | Unified | Scattered | Why |
|---|---:|---:|---:|---|
| One-shot token efficiency | 10 | 2 | 5 | Narrow CLI loads less guidance |
| Iterative token efficiency | 20 | 5 | 2 | Persistent in-process objects avoid repeated state/data |
| Cross-domain handoff | 15 | 5 | 2 | DataFrame/workbook/artifact references stay in one session |
| Agent discoverability | 10 | 4 | 3 | One grammar reduces selection; profile selection still matters |
| Output/error consistency | 10 | 5 | 2 | One event envelope and exit-code taxonomy |
| Security policy consistency | 10 | 5 | 2 | One state, environment, identity, timeout, and quota layer |
| Lifecycle/observability | 10 | 5 | 2 | Central status, interrupt, GC, logs, and audits |
| Install/update operations | 5 | 4 | 2 | One installer/Skill; adapters may remain modular |
| Domain-specific optimization | 5 | 3 | 5 | Dedicated CLIs can expose specialized operations directly |
| Fault/release isolation | 5 | 3 | 5 | Independent CLIs fail and ship independently |
| **Weighted total** | **100** | **87/100** | **54/100** | Unified wins for an Agent platform; scattered wins selective one-shot niches |

## Advantages beyond tokens

| Area | Unified advantage | Concrete effect |
|---|---|---|
| State | Kernel owns variables and live objects | Agent refers to `wb`/`df` rather than reconstructing them |
| Safety | One verified process lifecycle | No CLI invents its own PID files or kill behavior |
| Secrets | One environment allowlist | New runtimes inherit default-deny behavior |
| Timeouts | One interrupt/recovery contract | Agent knows whether state survived |
| Files | One source→working→output model | Fewer accidental source overwrites |
| Errors | Stable JSON envelope | Less branching and retry prompt logic |
| Artifacts | Common hashes/MIME/events | Large outputs stay outside model context |
| Audit | Unified event vocabulary | Easier monitoring, redaction, and compliance |
| Evolution | Adapter contract | JS/TS can reuse control-plane tests and policies |
| User experience | Natural-language Skill | Users do not learn seven commands or session schemes |

## Costs and risks of the unified design

| Risk | Consequence | Mitigation |
|---|---|---|
| Control-plane complexity | Adapter bugs can affect several runtimes | Contract tests and thin adapter boundary |
| Larger installation | Bundling Python, Node, LibreOffice, and future runtimes grows images | Modular runtime extras and profiles |
| Shared release cadence | A core change may delay one language | Versioned adapter API and independent adapter packages |
| Central blast radius | Registry/lifecycle defect affects all sessions | Schema migration, fail-closed process identity, canary release |
| Lowest-common-denominator API | Language-specific features may be hidden | Common envelope plus adapter-specific capabilities |
| Broad Skill context | One Skill can become token-heavy | Small router and lazy domain references |

## When scattered CLIs are the better choice

Use a dedicated CLI directly when all of these are true:

- the operation is one-shot and stateless;
- its input/output is already a file or compact identifier;
- it has a mature, stable, self-describing interface;
- no shared lifecycle or live object is needed;
- independent release/failure isolation matters more than one Agent grammar.

Examples include `git`, a deterministic file converter, formatter, compiler, or a narrow deployment CLI. Agent REPL should orchestrate computation and state; it should not wrap every existing command.

## Recommendation

Keep one public Agent contract:

```text
Skill -> agent-repl <profile> -> Runtime Adapter
```

Allow adapters to call mature dedicated CLIs internally and exchange large data through files/Arrow/Parquet rather than the model. This preserves domain specialization without exposing a fragmented session, security, and error model to the Agent.
