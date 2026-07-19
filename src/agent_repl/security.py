from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import psutil

try:
    import resource
except ImportError:  # pragma: no cover - Windows has no POSIX rlimits
    resource = None  # type: ignore[assignment]


SAFE_ENVIRONMENT = {
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "SHELL",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "TMPDIR",
    "TZ",
    "AGENT_REPL_SOFFICE",
}


def secure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except PermissionError:
        pass
    return path


def secure_write(path: Path, content: str) -> None:
    secure_directory(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    path.chmod(0o600)


def sanitized_environment(context_file: Path, process_token: str) -> dict[str, str]:
    allowed = set(SAFE_ENVIRONMENT)
    configured = os.environ.get("AGENT_REPL_ENV_ALLOWLIST", "")
    allowed.update(name.strip() for name in configured.split(",") if name.strip())
    environment = {name: value for name, value in os.environ.items() if name in allowed}
    environment.update(
        {
            "AGENT_REPL_CONTEXT": str(context_file),
            "AGENT_REPL_PROCESS_TOKEN": process_token,
            "PYTHONUNBUFFERED": "1",
        }
    )
    return environment


def _optional_limit(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw or raw == "0":
        return None
    value = int(raw)
    if value < 0:
        raise ValueError(f"{name} must be zero or a positive integer")
    return value


@dataclass(frozen=True)
class ResourceLimits:
    memory_mb: int | None = None
    cpu_seconds: int | None = None
    file_size_mb: int | None = None
    open_files: int | None = None
    processes: int | None = None

    @classmethod
    def from_environment(cls) -> "ResourceLimits":
        return cls(
            memory_mb=_optional_limit("AGENT_REPL_MAX_MEMORY_MB"),
            cpu_seconds=_optional_limit("AGENT_REPL_MAX_CPU_SECONDS"),
            file_size_mb=_optional_limit("AGENT_REPL_MAX_FILE_MB"),
            open_files=_optional_limit("AGENT_REPL_MAX_OPEN_FILES"),
            processes=_optional_limit("AGENT_REPL_MAX_PROCESSES"),
        )

    def enabled(self) -> dict[str, int]:
        return {
            name: value
            for name, value in {
                "memory_mb": self.memory_mb,
                "cpu_seconds": self.cpu_seconds,
                "file_size_mb": self.file_size_mb,
                "open_files": self.open_files,
                "processes": self.processes,
            }.items()
            if value is not None
        }


def resource_limiter(limits: ResourceLimits) -> Callable[[], None] | None:
    configured = limits.enabled()
    if not configured or os.name != "posix" or resource is None:
        return None

    def apply() -> None:
        mappings: list[tuple[int, int | None]] = [
            (resource.RLIMIT_CPU, limits.cpu_seconds),
            (resource.RLIMIT_FSIZE, limits.file_size_mb * 1024 * 1024 if limits.file_size_mb else None),
            (resource.RLIMIT_NOFILE, limits.open_files),
        ]
        if hasattr(resource, "RLIMIT_AS"):
            mappings.append((resource.RLIMIT_AS, limits.memory_mb * 1024 * 1024 if limits.memory_mb else None))
        if hasattr(resource, "RLIMIT_NPROC"):
            mappings.append((resource.RLIMIT_NPROC, limits.processes))
        for kind, requested in mappings:
            if requested is None:
                continue
            _, hard = resource.getrlimit(kind)
            effective = requested if hard == resource.RLIM_INFINITY else min(requested, hard)
            resource.setrlimit(kind, (effective, effective))

    return apply


def process_snapshot(pid: int) -> tuple[float, list[str]]:
    process = psutil.Process(pid)
    return process.create_time(), process.cmdline()


def process_matches(
    pid: int,
    expected_create_time: float,
    connection_file: Path,
    expected_token: str,
) -> bool:
    try:
        process = psutil.Process(pid)
        if abs(process.create_time() - expected_create_time) > 0.01:
            return False
        command = process.cmdline()
        expected = str(connection_file.resolve())
        if "ipykernel_launcher" not in " ".join(command) or expected not in command:
            return False
        return bool(expected_token) and process.environ().get("AGENT_REPL_PROCESS_TOKEN") == expected_token
    except (psutil.Error, OSError):
        return False


def default_runtime_root() -> Path:
    explicit = os.environ.get("AGENT_REPL_STATE_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime).resolve() / "agent-repl"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "agent-repl" / "runtime"
    cache = os.environ.get("XDG_CACHE_HOME")
    return (Path(cache).expanduser() if cache else Path.home() / ".cache") / "agent-repl" / "runtime"


def detected_agent_task_id() -> str | None:
    """Find a stable local Agent host identity when no host ID was injected."""

    try:
        process = psutil.Process(os.getpid()).parent()
        while process:
            command = " ".join(process.cmdline()).lower()
            name = process.name().lower()
            host = next((candidate for candidate in ("claude", "codex") if candidate in name or candidate in command), None)
            if host:
                return f"{host}-{process.pid}-{int(process.create_time())}"
            process = process.parent()
    except psutil.Error:
        return None
    return None
