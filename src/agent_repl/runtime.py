from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PythonRuntime:
    name: str = "python"
    language: str = "python"
    bootstrap: str = "from agent_repl_sdk import ctx"
    capabilities: tuple[str, ...] = ("python", "artifacts", "outputs")


RUNTIME = PythonRuntime()


LEGACY_ALIASES = {"py", "data", "excel"}


def parse_legacy_target(value: str) -> tuple[str, str | None] | None:
    alias, separator, session = value.partition("@")
    if alias not in LEGACY_ALIASES:
        return None
    if separator and not session:
        raise ValueError("Session name cannot be empty")
    return alias, session if separator else None


def legacy_prelude(alias: str | None) -> str:
    """Keep v0.2 commands working without making aliases runtime identities."""
    if alias == "data":
        return (
            "import numpy as np\n"
            "import pandas as pd\n"
            "pd.set_option('display.max_rows', 100)\n"
            "pd.set_option('display.max_columns', 50)"
        )
    if alias == "excel":
        return "from agent_repl_excel import ExcelWorkbook, excel"
    return ""
