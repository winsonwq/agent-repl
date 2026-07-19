# Token Cost Benchmark

Tokenizer: `tiktoken cl100k_base`

> These are reproducible context-size estimates, not provider billing guarantees. Tokenizers differ by model.

## Context and workflow

| Metric | Unified | Fragmented | Difference | Unified reduction |
|---|---:|---:|---:|---:|
| Always-visible discovery metadata | 125 | 138 | +13 | 9.4% |
| Main Skill guidance loaded | 526 | 461 | -65 | -14.1% |
| Four-step Excel commands only | 124 | 148 | +24 | 16.2% |
| Four-step Excel workflow (guidance + commands) | 650 | 344 | -306 | -89.0% |
| Excel-to-DataFrame workflow with artifact handoff | 650 | 367 | -283 | -77.1% |
| Mixed workflow with 10-row JSON handoff | 650 | 745 | +95 | 12.8% |
| Mixed workflow with 100-row JSON handoff | 650 | 4,318 | +3,668 | 84.9% |
| Mixed workflow with 1,000-row JSON handoff | 650 | 40,318 | +39,668 | 98.4% |

## Model-mediated tabular handoff

| Rows × 8 columns | JSON tokens | Artifact reference tokens | Avoided by shared state |
|---:|---:|---:|---:|
| 10 | 392 | 23 | 392 |
| 100 | 3,965 | 23 | 3,965 |
| 1,000 | 39,965 | 23 | 39,965 |
