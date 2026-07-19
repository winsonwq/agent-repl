from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jupyter_client.connect import write_connection_file

from .executor import ExecutionTimeout, connect_client, execute_code
from .locking import file_lock
from .models import SessionRecord
from .runtime import PythonRuntime
from .security import (
    ResourceLimits,
    process_matches,
    process_snapshot,
    resource_limiter,
    sanitized_environment,
    secure_directory,
    secure_write,
)


SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_id(value: str) -> str:
    cleaned = SAFE_ID.sub("-", value).strip("-.")
    if not cleaned:
        raise ValueError("Session identifier contains no usable characters")
    return cleaned[:120]


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


class SessionStore:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir.resolve()
        secure_directory(self.state_dir)
        self.sessions_dir = self.state_dir / "sessions"
        self.connections_dir = self.state_dir / "connections"
        self.logs_dir = self.state_dir / "logs"
        self.artifacts_dir = self.state_dir / "artifacts"
        self.contexts_dir = self.state_dir / "contexts"
        for path in (
            self.sessions_dir,
            self.connections_dir,
            self.logs_dir,
            self.artifacts_dir,
            self.contexts_dir,
        ):
            secure_directory(path)

    def record_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{safe_id(session_id)}.json"

    def lock_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{safe_id(session_id)}.lock"

    def load(self, session_id: str) -> SessionRecord | None:
        path = self.record_path(session_id)
        if not path.exists():
            return None
        record = SessionRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if record.session_id != session_id:
            raise RuntimeError("Session record identity mismatch")
        self._managed_path(record.connection_file, self.connections_dir)
        self._managed_path(record.context_file, self.contexts_dir)
        return record

    def save(self, record: SessionRecord) -> None:
        path = self.record_path(record.session_id)
        temporary = path.with_suffix(".tmp")
        secure_write(temporary, json.dumps(record.to_dict(), indent=2))
        temporary.replace(path)
        path.chmod(0o600)

    def list(self) -> list[SessionRecord]:
        records: list[SessionRecord] = []
        for path in sorted(self.sessions_dir.glob("*.json")):
            try:
                record = SessionRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
                self._managed_path(record.connection_file, self.connections_dir)
                self._managed_path(record.context_file, self.contexts_dir)
                records.append(record)
            except (OSError, ValueError, TypeError):
                continue
        return records

    def ensure(
        self,
        session_id: str,
        logical_session: str,
        runtime: PythonRuntime,
        workdir: Path,
    ) -> tuple[SessionRecord, bool]:
        with file_lock(self.lock_path(session_id)):
            existing = self.load(session_id)
            if existing and self._record_process_matches(existing):
                return existing, False
            if existing:
                self.record_path(session_id).unlink(missing_ok=True)
            return self._start(session_id, logical_session, runtime, workdir), True

    def _start(
        self,
        session_id: str,
        logical_session: str,
        runtime: PythonRuntime,
        workdir: Path,
    ) -> SessionRecord:
        encoded_id = safe_id(session_id)
        connection_file = self.connections_dir / f"{encoded_id}.json"
        context_file = self.contexts_dir / f"{encoded_id}.json"
        events_file = self.logs_dir / f"{encoded_id}-events.jsonl"
        artifact_dir = self.artifacts_dir / encoded_id
        workspace = workdir.resolve()
        context = {
            "task_id": os.environ.get("AGENT_TASK_ID", "default"),
            "session_id": session_id,
            "runtime": runtime.name,
            "language": runtime.language,
            "network_enabled": os.environ.get("AGENT_REPL_NETWORK_ENABLED") == "1",
            "security_boundary": (
                "host-sandbox-enforced"
                if os.environ.get("AGENT_REPL_SANDBOX_ENFORCED") == "1"
                else "local-process-only"
            ),
            "paths": {
                "inputs": str(workspace / "inputs"),
                "working": str(workspace / "working"),
                "outputs": str(workspace / "outputs"),
                "artifacts": str(workspace / "artifacts"),
                "temp": str(workspace / "temp"),
            },
            "capabilities": list(runtime.capabilities),
            "events_file": str(events_file),
        }
        for path in context["paths"].values():
            Path(path).mkdir(parents=True, exist_ok=True)
        secure_write(context_file, json.dumps(context, indent=2))
        write_connection_file(
            fname=str(connection_file),
            ip="127.0.0.1",
            # Jupyter serializes this byte string as UTF-8 in the connection
            # file, so use cryptographically random ASCII rather than raw bytes.
            key=secrets.token_hex(32).encode("ascii"),
            kernel_name="python3",
        )
        kernel_log = open(self.logs_dir / f"{encoded_id}-kernel.log", "ab", buffering=0)
        process_token = secrets.token_hex(32)
        environment = sanitized_environment(context_file, process_token)
        limits = ResourceLimits.from_environment()
        process = subprocess.Popen(
            [sys.executable, "-m", "ipykernel_launcher", "-f", str(connection_file)],
            cwd=workspace,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=kernel_log,
            stderr=kernel_log,
            start_new_session=True,
            close_fds=True,
            preexec_fn=resource_limiter(limits),
        )
        kernel_log.close()
        process_create_time, _ = process_snapshot(process.pid)
        now = datetime.now(timezone.utc).isoformat()
        record = SessionRecord(
            session_id=session_id,
            logical_session=logical_session,
            runtime_name=runtime.name,
            language=runtime.language,
            pid=process.pid,
            connection_file=str(connection_file),
            context_file=str(context_file),
            workdir=str(workspace),
            created_at=now,
            process_create_time=process_create_time,
            process_token=process_token,
            last_used_at=now,
        )
        try:
            client = connect_client(str(connection_file), ready_timeout=15)
            client.stop_channels()
            result = execute_code(str(connection_file), runtime.bootstrap, artifact_dir, timeout=30)
            if not result["ok"]:
                raise RuntimeError(f"Runtime bootstrap failed: {result['events']}")
        except Exception:
            self._terminate_known_child(process.pid)
            connection_file.unlink(missing_ok=True)
            context_file.unlink(missing_ok=True)
            raise
        self.save(record)
        return record

    def execute(self, record: SessionRecord, code: str, timeout: float) -> dict[str, Any]:
        with file_lock(self.lock_path(record.session_id), timeout=timeout + 10):
            if not self._record_process_matches(record):
                raise RuntimeError("SESSION_STATE_LOST: kernel process is no longer running")
            try:
                result = execute_code(
                    record.connection_file,
                    code,
                    self.artifacts_dir / safe_id(record.session_id),
                    timeout=timeout,
                )
            except ExecutionTimeout as exc:
                recovered = self._interrupt_and_wait(record, grace=5)
                exc.session_recovered = recovered
                if not recovered:
                    self._terminate_record(record)
                    self._remove_record_files(record)
                raise
            record.last_used_at = datetime.now(timezone.utc).isoformat()
            self.save(record)
            return result

    def stop(self, session_id: str) -> bool:
        with file_lock(self.lock_path(session_id)):
            record = self.load(session_id)
            if not record:
                return False
            stopped = self._terminate_record(record)
            self._remove_record_files(record)
            return stopped

    def is_healthy(self, record: SessionRecord) -> bool:
        return self._record_process_matches(record)

    @staticmethod
    def _terminate_known_child(pid: int) -> None:
        if not process_alive(pid):
            return
        try:
            if os.name == "posix":
                os.killpg(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not process_alive(pid):
                return
            time.sleep(0.05)
        try:
            if os.name == "posix":
                os.killpg(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def _managed_path(self, value: str, root: Path) -> Path:
        path = Path(value).resolve()
        resolved_root = root.resolve()
        if path.parent != resolved_root:
            raise RuntimeError(f"Session record references an unmanaged path: {path}")
        return path

    def _record_process_matches(self, record: SessionRecord) -> bool:
        try:
            connection_file = self._managed_path(record.connection_file, self.connections_dir)
            return connection_file.is_file() and process_matches(
                record.pid,
                record.process_create_time,
                connection_file,
                record.process_token,
            )
        except (OSError, RuntimeError):
            return False

    def _terminate_record(self, record: SessionRecord) -> bool:
        if not self._record_process_matches(record):
            return False
        self._terminate_known_child(record.pid)
        return True

    def _remove_record_files(self, record: SessionRecord) -> None:
        self.record_path(record.session_id).unlink(missing_ok=True)
        for value, root in (
            (record.connection_file, self.connections_dir),
            (record.context_file, self.contexts_dir),
        ):
            try:
                self._managed_path(value, root).unlink(missing_ok=True)
            except RuntimeError:
                continue

    def _interrupt_and_wait(self, record: SessionRecord, grace: float) -> bool:
        if not self._record_process_matches(record):
            return False
        try:
            if os.name == "posix":
                os.killpg(record.pid, signal.SIGINT)
            else:
                os.kill(record.pid, signal.SIGINT)
            client = connect_client(record.connection_file, ready_timeout=grace)
            client.stop_channels()
            return True
        except (OSError, RuntimeError, TimeoutError):
            return False

    def clean(self) -> int:
        stopped = 0
        for record in self.list():
            if self.stop(record.session_id):
                stopped += 1
        return stopped

    def gc(self, stale_minutes: int) -> int:
        if stale_minutes < 1:
            raise ValueError("stale_minutes must be at least 1")
        now = datetime.now(timezone.utc)
        removed = 0
        for record in self.list():
            timestamp = record.last_used_at or record.created_at
            try:
                idle_seconds = (now - datetime.fromisoformat(timestamp)).total_seconds()
            except ValueError:
                idle_seconds = stale_minutes * 60 + 1
            if idle_seconds >= stale_minutes * 60:
                self.stop(record.session_id)
                removed += 1
        return removed
