# Token Cost Benchmark

Tokenizer: `tiktoken cl100k_base`

> These are reproducible context-size estimates, not provider billing guarantees. Tokenizers differ by model.

## Context and workflow

| Metric | Unified | Fragmented | Difference | Unified reduction |
|---|---:|---:|---:|---:|
| Always-visible discovery metadata | 126 | 138 | +12 | 8.7% |
| All capability guidance loaded | 677 | 461 | -216 | -46.9% |
| Four-step Excel commands only | 112 | 148 | +36 | 24.3% |
| Four-step Excel workflow (guidance + commands) | 789 | 344 | -445 | -129.4% |
| Excel-to-DataFrame workflow with artifact handoff | 786 | 367 | -419 | -114.2% |
| Mixed workflow with 10-row JSON handoff | 786 | 745 | -41 | -5.5% |
| Mixed workflow with 100-row JSON handoff | 786 | 4,318 | +3,532 | 81.8% |
| Mixed workflow with 1,000-row JSON handoff | 786 | 40,318 | +39,532 | 98.1% |

## Model-mediated tabular handoff

| Rows × 8 columns | JSON tokens | Artifact reference tokens | Avoided by shared state |
|---:|---:|---:|---:|
| 10 | 392 | 23 | 392 |
| 100 | 3,965 | 23 | 3,965 |
| 1,000 | 39,965 | 23 | 39,965 |
