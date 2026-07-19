from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FileRef:
    name: str
    path: Path

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "path": str(self.path)}


class PathArea:
    def __init__(self, root: Path, events: "EventEmitter", area: str):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.events = events
        self.area = area

    def _resolve(self, name: str) -> Path:
        candidate = (self.root / name).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError(f"Path escapes {self.area} area: {name}")
        return candidate

    def list(self) -> list[FileRef]:
        return [FileRef(path.name, path) for path in sorted(self.root.iterdir()) if path.is_file()]

    def get(self, name: str) -> FileRef:
        path = self._resolve(name)
        if not path.is_file():
            raise FileNotFoundError(f"No such {self.area} file: {name}")
        self.events.emit("file_read", area=self.area, path=str(path))
        return FileRef(path.name, path)

    def path(self, name: str) -> Path:
        return self._resolve(name)

    def copy_from(self, source: FileRef | Path | str, name: str | None = None) -> FileRef:
        source_path = Path(source.path if isinstance(source, FileRef) else source).resolve()
        destination = self._resolve(name or source_path.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        self.events.emit("file_created", area=self.area, path=str(destination), source=str(source_path))
        return FileRef(destination.name, destination)


class EventEmitter:
    def __init__(self, events_file: Path | None):
        self.events_file = events_file

    def emit(self, event_type: str, **data: Any) -> dict[str, Any]:
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        if self.events_file:
            self.events_file.parent.mkdir(parents=True, exist_ok=True)
            with self.events_file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        return event

    def warning(self, message: str, **data: Any) -> dict[str, Any]:
        return self.emit("warning", message=message, **data)


class Publisher:
    def __init__(self, area: PathArea, events: EventEmitter, event_type: str):
        self.area = area
        self.events = events
        self.event_type = event_type

    def publish_file(
        self,
        path: Path | str,
        *,
        name: str | None = None,
        media_type: str | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        source = Path(path).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = self.area.path(name or source.name)
        if source != destination:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        record = {
            "name": destination.name,
            "path": str(destination),
            "media_type": media_type or mimetypes.guess_type(destination.name)[0] or "application/octet-stream",
            "title": title or destination.name,
            "size": destination.stat().st_size,
            "sha256": digest,
        }
        self.events.emit(self.event_type, **record)
        return record

    publish = publish_file


class Capabilities:
    def __init__(self, values: list[str]):
        self._values = tuple(values)

    def list(self) -> list[str]:
        return list(self._values)

    def has(self, name: str) -> bool:
        return name in self._values


class RuntimeContext:
    def __init__(self, value: dict[str, Any]):
        self._value = value
        paths = value["paths"]
        self.events = EventEmitter(Path(value["events_file"]) if value.get("events_file") else None)
        self.inputs = PathArea(Path(paths["inputs"]), self.events, "inputs")
        self.working = PathArea(Path(paths["working"]), self.events, "working")
        outputs_area = PathArea(Path(paths["outputs"]), self.events, "outputs")
        artifacts_area = PathArea(Path(paths["artifacts"]), self.events, "artifacts")
        self.outputs = Publisher(outputs_area, self.events, "output_published")
        self.artifacts = Publisher(artifacts_area, self.events, "artifact_published")
        self.paths = {name: Path(path) for name, path in paths.items()}
        self.capabilities = Capabilities(value.get("capabilities", []))

    @classmethod
    def load(cls) -> "RuntimeContext":
        context_file = os.environ.get("AGENT_REPL_CONTEXT")
        if context_file:
            return cls(json.loads(Path(context_file).read_text(encoding="utf-8")))
        workspace = Path.cwd()
        value = {
            "task_id": os.environ.get("AGENT_TASK_ID", "default"),
            "session_id": "standalone",
            "runtime": "python",
            "language": "python",
            "network_enabled": True,
            "paths": {
                name: str(workspace / name)
                for name in ("inputs", "working", "outputs", "artifacts", "temp")
            },
            "capabilities": ["python", "artifacts", "outputs"],
            "events_file": None,
        }
        return cls(value)

    @property
    def session_id(self) -> str:
        return str(self._value["session_id"])

    @property
    def runtime(self) -> str:
        return str(self._value.get("runtime", self._value.get("profile", "python")))

    @property
    def profile(self) -> str:
        """Backward-compatible alias for runtime."""
        return self.runtime

    def describe(self) -> dict[str, Any]:
        return {
            "task_id": self._value["task_id"],
            "session_id": self._value["session_id"],
            "runtime": self.runtime,
            "language": self._value["language"],
            "network_enabled": self._value["network_enabled"],
        } | {
            "security_boundary": self._value.get("security_boundary", "unknown"),
            "paths": {key: str(value) for key, value in self.paths.items()},
            "capabilities": self.capabilities.list(),
        }
