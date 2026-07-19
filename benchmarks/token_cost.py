#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]


SCATTERED_CLIS = {
    "python-repl": {
        "description": "Run Python snippets in a named persistent Python process and manage Python session state.",
        "help": """# python-repl
Use for iterative Python work. Start or reconnect with `python-repl exec --session <name> --stdin --json`. Inspect with `python-repl status --session <name>`. Stop with `python-repl stop --session <name>`. Success and error records are JSON. Reuse the exact session name. Published files require a separate artifact command.""",
    },
    "javascript-repl": {
        "description": "Run JavaScript snippets in a persistent Node.js process and manage JavaScript state.",
        "help": """# javascript-repl
Use for iterative JavaScript and Node.js work. Call `javascript-repl exec --session <name> --stdin --format json`. The session namespace is independent from Python and TypeScript. Await promises before returning. Use the separate session manager to interrupt, restart, or clean the process.""",
    },
    "typescript-repl": {
        "description": "Transpile and run TypeScript snippets in a named persistent TypeScript process.",
        "help": """# typescript-repl
Use for iterative TypeScript. Call `typescript-repl exec --session <name> --project <path> --stdin --json`. Choose transpile-only or type-check mode. Preserve the generated JavaScript context between calls. Source maps and compiler errors use TypeScript-specific result fields.""",
    },
    "dataframe-cli": {
        "description": "Create, transform, aggregate, and export tabular data through stateless DataFrame commands.",
        "help": """# dataframe-cli
Use for CSV and tabular transformations. Every call requires `--input` and normally writes `--output`; the process does not retain DataFrames. Commands include inspect, filter, mutate, group, join, and chart. Pass intermediate files or JSON records between commands and inspect the command-specific error schema.""",
    },
    "excel-cli": {
        "description": "Inspect and modify Excel workbooks with separate commands for cells, formulas, calculation, and validation.",
        "help": """# excel-cli
Use for xlsx and xlsm files. Each invocation requires an input path and output path. Use `excel-cli inspect`, `excel-cli set-cell`, `excel-cli set-formula`, `excel-cli recalculate`, and `excel-cli validate`. Never overwrite the original. Track the latest intermediate filename across commands. Publication is handled by artifact-cli.""",
    },
    "artifact-cli": {
        "description": "Publish a local result file, compute metadata, and return an Agent-readable artifact record.",
        "help": """# artifact-cli
Publish durable outputs with `artifact-cli publish --file <path> --output-dir <dir> --json`. It returns name, media type, size, SHA-256, and path. This CLI does not know which runtime created the file; the caller must pass the correct latest intermediate path.""",
    },
    "session-cli": {
        "description": "List, inspect, interrupt, restart, expire, and stop persistent language runtime processes.",
        "help": """# session-cli
Manage process lifecycle with `session-cli <status|interrupt|restart|stop|gc> --runtime <kind> --session <name> --json`. Runtime identifiers and session identifiers must match those used by the language-specific CLI. Error and health fields differ by runtime adapter.""",
    },
}


UNIFIED_EXCEL_COMMANDS = """agent-repl excel --json <<'PY'
wb = excel.open('report.xlsx')
wb.read_range('Sales!A1:D20')
PY
agent-repl excel --json <<'PY'
wb.set_value('Sales!B6', 1800)
wb.set_formula('Sales!D6', '=B6-C6')
PY
agent-repl excel --json <<'PY'
wb.recalculate()
wb.scan_formula_errors()
PY
agent-repl excel --json <<'PY'
wb.save_output('report-updated.xlsx')
PY"""


SCATTERED_EXCEL_COMMANDS = """excel-cli inspect --input report.xlsx --range 'Sales!A1:D20' --json
excel-cli set-cell --input report.xlsx --output working/report-step1.xlsx --cell 'Sales!B6' --value 1800 --json
excel-cli set-formula --input working/report-step1.xlsx --output working/report-step2.xlsx --cell 'Sales!D6' --formula '=B6-C6' --json
excel-cli recalculate --input working/report-step2.xlsx --output working/report-step3.xlsx --json
excel-cli validate --input working/report-step3.xlsx --formula-errors --json
artifact-cli publish --file working/report-step3.xlsx --output-dir outputs --name report-updated.xlsx --json"""


UNIFIED_MIXED_COMMANDS = """agent-repl excel --json <<'PY'
wb = excel.open('sales.xlsx')
rows = wb.read_range('Sales!A1:H101')
df = pd.DataFrame(rows[1:], columns=rows[0])
summary = df.groupby('region', as_index=False).revenue.sum()
summary
PY
agent-repl excel --json <<'PY'
summary.to_excel(ctx.paths['outputs'] / 'regional-summary.xlsx', index=False)
ctx.outputs.publish_file(ctx.paths['outputs'] / 'regional-summary.xlsx')
PY"""


SCATTERED_MIXED_COMMANDS = """excel-cli export-range --input sales.xlsx --range 'Sales!A1:H101' --output temp/sales.csv --json
dataframe-cli group --input temp/sales.csv --by region --sum revenue --output temp/regional-summary.csv --json
dataframe-cli export-excel --input temp/regional-summary.csv --output working/regional-summary.xlsx --json
artifact-cli publish --file working/regional-summary.xlsx --output-dir outputs --json"""


def tokenizer() -> tuple[Callable[[str], int], str]:
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        return lambda value: len(encoding.encode(value)), "tiktoken cl100k_base"
    except Exception:
        return lambda value: math.ceil(len(value.encode("utf-8")) / 4), "UTF-8 bytes / 4 fallback"


def table_payload(rows: int) -> str:
    regions = ("East", "West", "North", "South")
    value = [
        {
            "month": f"2026-{(index % 12) + 1:02d}",
            "region": regions[index % len(regions)],
            "product": f"SKU-{index % 25:03d}",
            "revenue": 1000 + index * 17,
            "cost": 600 + index * 11,
            "units": 10 + index % 40,
            "channel": "branch" if index % 2 else "mobile",
            "approved": index % 3 != 0,
        }
        for index in range(rows)
    ]
    return json.dumps(value, separators=(",", ":"))


def comparison(unified: int, fragmented: int) -> dict[str, float | int]:
    delta = fragmented - unified
    return {
        "unified_tokens": unified,
        "fragmented_tokens": fragmented,
        "fragmented_minus_unified": delta,
        "unified_reduction_pct": round(delta / fragmented * 100, 1) if fragmented else 0,
    }


def render_markdown(result: dict) -> str:
    lines = [
        "# Token Cost Benchmark",
        "",
        f"Tokenizer: `{result['method']['tokenizer']}`",
        "",
        "> These are reproducible context-size estimates, not provider billing guarantees. Tokenizers differ by model.",
        "",
        "## Context and workflow",
        "",
        "| Metric | Unified | Fragmented | Difference | Unified reduction |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in result["comparisons"]:
        lines.append(
            f"| {row['name']} | {row['unified_tokens']:,} | {row['fragmented_tokens']:,} | "
            f"{row['fragmented_minus_unified']:+,} | {row['unified_reduction_pct']:.1f}% |"
        )
    lines.extend(
        [
            "",
            "## Model-mediated tabular handoff",
            "",
            "| Rows × 8 columns | JSON tokens | Artifact reference tokens | Avoided by shared state |",
            "|---:|---:|---:|---:|",
        ]
    )
    for row in result["handoff"]:
        lines.append(
            f"| {row['rows']:,} | {row['json_tokens']:,} | {row['artifact_reference_tokens']:,} | "
            f"{row['shared_state_tokens_avoided']:,} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare prompt/context token costs for unified and scattered Agent CLIs.")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "benchmarks" / "results")
    args = parser.parse_args()
    count, method = tokenizer()

    unified_skill = (PROJECT_ROOT / "skills" / "agent-repl" / "SKILL.md").read_text(encoding="utf-8")
    unified_metadata = unified_skill.split("---", 2)[1]
    scattered_metadata = "\n".join(
        f"{name}: {value['description']}" for name, value in SCATTERED_CLIS.items()
    )
    fragmented_all_guidance = "\n".join(value["help"] for value in SCATTERED_CLIS.values())
    fragmented_excel_guidance = "\n".join(
        SCATTERED_CLIS[name]["help"] for name in ("excel-cli", "artifact-cli", "session-cli")
    )
    fragmented_mixed_guidance = "\n".join(
        SCATTERED_CLIS[name]["help"]
        for name in ("excel-cli", "dataframe-cli", "artifact-cli", "session-cli")
    )

    comparison_inputs = [
        ("Always-visible discovery metadata", count(unified_metadata), count(scattered_metadata)),
        ("All capability guidance loaded", count(unified_skill), count(fragmented_all_guidance)),
        ("Four-step Excel commands only", count(UNIFIED_EXCEL_COMMANDS), count(SCATTERED_EXCEL_COMMANDS)),
        (
            "Four-step Excel workflow (guidance + commands)",
            count(unified_skill) + count(UNIFIED_EXCEL_COMMANDS),
            count(fragmented_excel_guidance) + count(SCATTERED_EXCEL_COMMANDS),
        ),
        (
            "Excel-to-DataFrame workflow with artifact handoff",
            count(unified_skill) + count(UNIFIED_MIXED_COMMANDS),
            count(fragmented_mixed_guidance)
            + count(SCATTERED_MIXED_COMMANDS)
            + count("artifact: temp/sales.csv -> artifact: temp/regional-summary.csv"),
        ),
    ]

    artifact_reference = count(
        '{"artifact":{"path":"temp/sales.csv","sha256":"0123456789abcdef","rows":100}}'
    )
    handoff = []
    fragmented_mixed_base = count(fragmented_mixed_guidance) + count(SCATTERED_MIXED_COMMANDS)
    unified_mixed_base = count(unified_skill) + count(UNIFIED_MIXED_COMMANDS)
    for rows in (10, 100, 1000):
        json_tokens = count(table_payload(rows))
        handoff.append(
            {
                "rows": rows,
                "columns": 8,
                "json_tokens": json_tokens,
                "artifact_reference_tokens": artifact_reference,
                "shared_state_tokens_avoided": json_tokens,
            }
        )
        comparison_inputs.append(
            (
                f"Mixed workflow with {rows:,}-row JSON handoff",
                unified_mixed_base,
                fragmented_mixed_base + json_tokens,
            )
        )

    comparisons = []
    for name, unified, fragmented in comparison_inputs:
        comparisons.append({"name": name, **comparison(unified, fragmented)})

    result = {
        "method": {
            "tokenizer": method,
            "warning": "Relative context estimate only; model providers and model versions tokenize differently.",
            "fragmented_definition": "Seven separately documented CLIs for Python, JavaScript, TypeScript, DataFrame, Excel, artifacts, and session lifecycle.",
            "unified_definition": "One agent-repl grammar, Skill, output contract, lifecycle, and persistent runtime routing.",
        },
        "comparisons": comparisons,
        "handoff": handoff,
        "raw": {
            "unified_skill_tokens": count(unified_skill),
            "fragmented_all_guidance_tokens": count(fragmented_all_guidance),
            "unified_excel_command_tokens": count(UNIFIED_EXCEL_COMMANDS),
            "fragmented_excel_command_tokens": count(SCATTERED_EXCEL_COMMANDS),
            "unified_mixed_command_tokens": count(UNIFIED_MIXED_COMMANDS),
            "fragmented_mixed_command_tokens": count(SCATTERED_MIXED_COMMANDS),
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "token-cost.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (args.output_dir / "token-cost.md").write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps({"status": "ok", "data": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
