from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SessionRecord:
    session_id: str
    logical_session: str
    runtime_name: str
    language: str
    pid: int
    connection_file: str
    context_file: str
    workdir: str
    created_at: str
    process_create_time: float = 0.0
    process_token: str = ""
    last_used_at: str = ""
    schema_version: int = 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SessionRecord":
        migrated = dict(value)
        migrated.setdefault("runtime_name", migrated.pop("profile_name", "python"))
        migrated.pop("profile_alias", None)
        migrated.setdefault("schema_version", 1)
        return cls(**migrated)
