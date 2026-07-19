from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    alias: str
    name: str
    language: str
    bootstrap: str
    capabilities: tuple[str, ...]


PROFILES: dict[str, Profile] = {
    "py": Profile(
        alias="py",
        name="python-base",
        language="python",
        bootstrap="from agent_repl_sdk import ctx",
        capabilities=("python", "artifacts", "outputs"),
    ),
    "data": Profile(
        alias="data",
        name="python-data",
        language="python",
        bootstrap=(
            "from agent_repl_sdk import ctx\n"
            "import numpy as np\n"
            "import pandas as pd\n"
            "pd.set_option('display.max_rows', 100)\n"
            "pd.set_option('display.max_columns', 50)"
        ),
        capabilities=("python", "dataframe", "artifacts", "outputs"),
    ),
    "excel": Profile(
        alias="excel",
        name="python-excel",
        language="python",
        bootstrap=(
            "from agent_repl_sdk import ctx\n"
            "from agent_repl_excel import ExcelWorkbook, excel"
        ),
        capabilities=(
            "python",
            "excel.read",
            "excel.write",
            "excel.recalculate",
            "excel.validate",
            "artifacts",
            "outputs",
        ),
    ),
}


def resolve_profile(alias: str) -> Profile:
    try:
        return PROFILES[alias]
    except KeyError as exc:
        choices = ", ".join(sorted(PROFILES))
        raise ValueError(f"Unknown runtime '{alias}'. Available: {choices}") from exc


def parse_target(target: str, default_session: str) -> tuple[Profile, str]:
    runtime, separator, explicit_session = target.partition("@")
    profile = resolve_profile(runtime)
    session = explicit_session if separator else default_session
    if not session:
        raise ValueError("Session name cannot be empty")
    return profile, session
