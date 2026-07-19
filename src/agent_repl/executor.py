from __future__ import annotations

import base64
import json
import queue
import time
from pathlib import Path
from typing import Any

from jupyter_client import BlockingKernelClient


class ExecutionTimeout(RuntimeError):
    pass


def connect_client(connection_file: str, ready_timeout: float = 10.0) -> BlockingKernelClient:
    client = BlockingKernelClient(connection_file=connection_file)
    client.load_connection_file()
    client.start_channels()
    client.wait_for_ready(timeout=ready_timeout)
    return client


def _save_artifact(
    artifacts_dir: Path,
    execution_count: int | None,
    index: int,
    mime_type: str,
    payload: str,
) -> dict[str, Any]:
    extensions = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "text/html": "html",
        "application/json": "json",
    }
    extension = extensions[mime_type]
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    name = f"cell-{execution_count or 0:04d}-output-{index}.{extension}"
    path = artifacts_dir / name
    if mime_type.startswith("image/"):
        path.write_bytes(base64.b64decode(payload))
    elif mime_type == "application/json":
        value = payload if isinstance(payload, (dict, list)) else json.loads(payload)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")
    return {"name": name, "path": str(path), "mime_type": mime_type, "size": path.stat().st_size}


def execute_code(
    connection_file: str,
    code: str,
    artifacts_dir: Path,
    timeout: float = 120.0,
    output_limit: int = 100_000,
) -> dict[str, Any]:
    client = connect_client(connection_file)
    started = time.monotonic()
    msg_id = client.execute(code, allow_stdin=False, stop_on_error=True)
    events: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    text_size = 0
    execution_count: int | None = None
    saw_idle = False
    try:
        while not saw_idle:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise ExecutionTimeout(f"Execution exceeded {timeout:.1f} seconds")
            try:
                message = client.get_iopub_msg(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if message.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            msg_type = message["msg_type"]
            content = message["content"]
            if msg_type == "status":
                saw_idle = content.get("execution_state") == "idle"
            elif msg_type == "execute_input":
                execution_count = content.get("execution_count")
            elif msg_type == "stream":
                text = content.get("text", "")
                allowed = max(0, output_limit - text_size)
                clipped = text[:allowed]
                text_size += len(clipped)
                events.append({"type": content.get("name", "stdout"), "text": clipped})
                if len(clipped) < len(text):
                    events.append({"type": "truncated", "original_chars": len(text)})
            elif msg_type in {"execute_result", "display_data"}:
                data = content.get("data", {})
                execution_count = content.get("execution_count", execution_count)
                plain = data.get("text/plain")
                if plain is not None:
                    allowed = max(0, output_limit - text_size)
                    clipped = str(plain)[:allowed]
                    text_size += len(clipped)
                    events.append({"type": "result" if msg_type == "execute_result" else "display", "mime_type": "text/plain", "text": clipped})
                for mime_type in ("image/png", "image/jpeg", "text/html", "application/json"):
                    if mime_type in data:
                        artifact = _save_artifact(
                            artifacts_dir,
                            execution_count,
                            len(artifacts) + 1,
                            mime_type,
                            data[mime_type],
                        )
                        artifacts.append(artifact)
                        events.append({"type": "artifact", **artifact})
            elif msg_type == "error":
                events.append(
                    {
                        "type": "error",
                        "name": content.get("ename", "Error"),
                        "message": content.get("evalue", ""),
                        "traceback": content.get("traceback", []),
                    }
                )

        reply: dict[str, Any] | None = None
        reply_deadline = time.monotonic() + 5
        while time.monotonic() < reply_deadline:
            try:
                candidate = client.get_shell_msg(timeout=1)
            except queue.Empty:
                continue
            if candidate.get("parent_header", {}).get("msg_id") == msg_id:
                reply = candidate
                break
        status = (reply or {}).get("content", {}).get("status", "ok")
        return {
            "ok": status == "ok" and not any(e["type"] == "error" for e in events),
            "execution_count": execution_count,
            "events": events,
            "artifacts": artifacts,
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
    finally:
        client.stop_channels()
