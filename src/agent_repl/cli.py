from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from .executor import ExecutionTimeout
from .runtime import RUNTIME, legacy_prelude, parse_legacy_target
from .security import ResourceLimits, default_runtime_root, detected_agent_task_id
from .sessions import SessionStore, safe_id


def success(data: Any) -> dict[str, Any]:
    return {"status": "ok", "data": data}


def failure(
    message: str,
    code: str = "GENERAL_ERROR",
    recoverable: bool = False,
    data: Any | None = None,
) -> dict[str, Any]:
    payload = {
        "status": "error",
        "error": {"code": code, "message": message, "recoverable": recoverable},
    }
    if data is not None:
        payload["data"] = data
    return payload


def emit(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
        return
    if payload["status"] == "error":
        print(f"error: {payload['error']['message']}", file=sys.stderr)
        return
    data = payload["data"]
    if isinstance(data, dict) and "events" in data:
        for event in data["events"]:
            if event["type"] in {"stdout", "stderr"}:
                stream = sys.stderr if event["type"] == "stderr" else sys.stdout
                print(event.get("text", ""), end="", file=stream)
            elif event["type"] in {"result", "display"}:
                print(event.get("text", ""))
            elif event["type"] == "error":
                print(f"{event.get('name')}: {event.get('message')}", file=sys.stderr)
            elif event["type"] == "artifact":
                print(f"[agent-repl artifact] {event['mime_type']} {event['path']}")
        return
    print(json.dumps(data, indent=2, ensure_ascii=False))


def state_dir_from(args: argparse.Namespace, workdir: Path | None = None) -> Path:
    explicit = getattr(args, "state_dir", None)
    if explicit:
        return Path(explicit).expanduser()
    configured_workdir = getattr(args, "workdir", None) or os.environ.get("AGENT_REPL_WORKDIR", ".")
    workspace = (workdir or Path(configured_workdir)).resolve()
    namespace = hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()[:20]
    configured_root = os.environ.get("AGENT_REPL_STATE_DIR")
    root = Path(configured_root).expanduser().resolve() if configured_root else default_runtime_root()
    return root / namespace


def default_json(args: argparse.Namespace) -> bool:
    if getattr(args, "json", False):
        return True
    return os.environ.get("AGENT_REPL_OUTPUT", "").lower() == "json"


def build_execute_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-repl",
        description="Execute code in a persistent, named Jupyter kernel session.",
        epilog=(
            "Examples:\n"
            "  agent-repl 'x = 41'\n"
            "  agent-repl 'x + 1'\n"
            "  agent-repl --session experiment-a --stdin < analyze.py"
            "\nLegacy py, data, and excel targets remain accepted as aliases."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("inputs", nargs="*", metavar="CODE", help="Python code; reads stdin when omitted")
    parser.add_argument("--session", help="Optional isolated logical session")
    parser.add_argument("--stdin", action="store_true", help="Read Python code from standard input")
    parser.add_argument("--file", help="Read code from a UTF-8 file")
    parser.add_argument("--workdir", default=os.environ.get("AGENT_REPL_WORKDIR", "."))
    parser.add_argument("--state-dir")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--json", action="store_true", help="Emit one JSON object")
    return parser


def build_management_parser(command: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"agent-repl {command}")
    if command in {"status", "stop", "restart"}:
        parser.add_argument("target", nargs="?", help="Legacy target such as py@demo")
        parser.add_argument("--session", help="Optional isolated logical session")
    parser.add_argument("--state-dir")
    parser.add_argument("--workdir", default=os.environ.get("AGENT_REPL_WORKDIR", "."))
    parser.add_argument("--json", action="store_true")
    if command == "gc":
        parser.add_argument("--stale-minutes", type=int, default=240)
    return parser


def task_identity() -> str:
    return next(
        (
            os.environ[name]
            for name in ("AGENT_TASK_ID", "CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")
            if os.environ.get(name)
        ),
        detected_agent_task_id() or "default",
    )


def session_identity(explicit_session: str | None) -> tuple[str, str]:
    task_id = safe_id(task_identity())
    logical_session = safe_id(explicit_session or "default")
    return logical_session, f"{task_id}:{logical_session}"


def execution_input(args: argparse.Namespace) -> tuple[str | None, str | None]:
    values = list(args.inputs)
    legacy_alias: str | None = None
    legacy_session: str | None = None
    if values:
        legacy = parse_legacy_target(values[0])
        if legacy:
            legacy_alias, legacy_session = legacy
            values.pop(0)
    if len(values) > 1:
        raise ValueError("Provide Python code as one argument or pipe it through stdin")
    if args.session and legacy_session:
        raise ValueError("Use either --session or an @session legacy alias, not both")
    if args.stdin and values:
        raise ValueError("Use either a code argument or --stdin, not both")
    if args.stdin and args.file:
        raise ValueError("Use either --file or --stdin, not both")
    return legacy_alias, args.session or legacy_session


def handle_execute(argv: list[str]) -> int:
    parser = build_execute_parser()
    args = parser.parse_args(argv)
    json_output = default_json(args)
    try:
        legacy_alias, explicit_session = execution_input(args)
        logical_session, session_id = session_identity(explicit_session)
        if args.file and args.inputs[1 if legacy_alias else 0 :]:
            raise ValueError("Use either a code argument or --file, not both")
        if args.file:
            code = Path(args.file).read_text(encoding="utf-8")
        elif args.inputs[1 if legacy_alias else 0 :]:
            code = args.inputs[-1]
        elif not sys.stdin.isatty():
            code = sys.stdin.read()
        else:
            raise ValueError("Provide code, --file, or pipe code through stdin")
        if not code.strip():
            raise ValueError("Code cannot be empty")
        prelude = legacy_prelude(legacy_alias)
        if prelude:
            code = f"{prelude}\n{code}"
        workdir = Path(args.workdir)
        store = SessionStore(state_dir_from(args, workdir))
        auto_gc_minutes = int(os.environ.get("AGENT_REPL_AUTO_GC_MINUTES", "1440"))
        if auto_gc_minutes > 0:
            store.gc(auto_gc_minutes)
        record, created = store.ensure(
            session_id,
            logical_session,
            RUNTIME,
            workdir,
        )
        result = store.execute(record, code, args.timeout)
        result.update(
            {
                "session": session_id,
                "runtime": RUNTIME.name,
                "created": created,
                "state_preserved": not created,
            }
        )
        if not result["ok"]:
            error_events = [event for event in result["events"] if event["type"] == "error"]
            message = error_events[-1].get("message", "Code execution failed") if error_events else "Code execution failed"
            emit(failure(message, "CODE_EXECUTION_ERROR", data=result), json_output)
            return 1
        emit(success(result), json_output)
        return 0
    except ExecutionTimeout as exc:
        recovered = bool(getattr(exc, "session_recovered", False))
        emit(
            failure(
                str(exc),
                "EXECUTION_TIMEOUT",
                recoverable=recovered,
                data={"session_recovered": recovered},
            ),
            json_output,
        )
        return 4
    except ValueError as exc:
        emit(failure(str(exc), "INVALID_ARGUMENT"), json_output)
        return 2
    except TimeoutError as exc:
        emit(failure(str(exc), "SESSION_BUSY", True), json_output)
        return 3
    except Exception as exc:
        message = str(exc)
        code = "SESSION_STATE_LOST" if "SESSION_STATE_LOST" in message else "EXECUTION_FAILED"
        emit(failure(message, code, code == "SESSION_STATE_LOST"), json_output)
        return 1


def handle_management(command: str, argv: list[str]) -> int:
    args = build_management_parser(command).parse_args(argv)
    json_output = default_json(args)
    store = SessionStore(state_dir_from(args))
    try:
        if command == "doctor":
            state_dir = store.state_dir
            workspace = Path(args.workdir).resolve()
            data = {
                "executable": shutil.which("agent-repl") or sys.argv[0],
                "python": sys.executable,
                "workspace": str(workspace),
                "state_dir": str(state_dir),
                "state_outside_workspace": workspace not in state_dir.parents and state_dir != workspace,
                "skill_locations": [
                    str(path)
                    for path in (
                        Path.home() / ".claude" / "skills" / "agent-repl" / "SKILL.md",
                        workspace / ".claude" / "skills" / "agent-repl" / "SKILL.md",
                    )
                    if path.is_file()
                ],
                "libreoffice": os.environ.get("AGENT_REPL_SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice"),
                "resource_limits": ResourceLimits.from_environment().enabled(),
                "sandbox_enforced": os.environ.get("AGENT_REPL_SANDBOX_ENFORCED") == "1",
            }
            data["ready"] = bool(data["executable"] and data["state_outside_workspace"])
            data["production_ready"] = bool(
                data["ready"]
                and data["sandbox_enforced"]
                and data["resource_limits"]
            )
            data["warnings"] = []
            if not data["skill_locations"]:
                data["warnings"].append("Agent Skill is not installed in a detected Claude project/user location")
            if not data["sandbox_enforced"]:
                data["warnings"].append("OS sandbox enforcement is not declared; arbitrary Python has host-user permissions")
            if not data["resource_limits"]:
                data["warnings"].append("No standalone Kernel resource limits are configured")
        elif command == "sessions":
            data = [
                {**record.to_dict(), "alive": store.is_healthy(record)}
                for record in store.list()
            ]
        elif command == "clean":
            data = {"stopped": store.clean()}
        elif command == "gc":
            data = {"removed": store.gc(args.stale_minutes), "stale_minutes": args.stale_minutes}
        else:
            legacy_session = None
            if args.target:
                legacy = parse_legacy_target(args.target)
                if not legacy:
                    raise ValueError(f"Unknown legacy target: {args.target}")
                _, legacy_session = legacy
            if args.session and legacy_session:
                raise ValueError("Use either --session or an @session legacy alias, not both")
            logical_session, session_id = session_identity(args.session or legacy_session)
            record = store.load(session_id)
            if command == "status":
                data = {
                    "session": session_id,
                    "exists": record is not None,
                    "alive": bool(record and store.is_healthy(record)),
                    "runtime": RUNTIME.name,
                }
            elif command == "stop":
                data = {"session": session_id, "stopped": store.stop(session_id)}
            elif command == "restart":
                store.stop(session_id)
                record, _ = store.ensure(
                    session_id,
                    logical_session,
                    RUNTIME,
                    Path(args.workdir),
                )
                data = {"session": session_id, "pid": record.pid, "restarted": True}
            else:
                raise ValueError(f"Unknown command: {command}")
        emit(success(data), json_output)
        return 0
    except Exception as exc:
        emit(failure(str(exc)), json_output)
        return 1


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        if sys.stdin.isatty():
            build_execute_parser().print_help()
            return 0
        return handle_execute([])
    if arguments[0] in {"status", "stop", "restart", "sessions", "clean", "gc", "doctor"}:
        return handle_management(arguments[0], arguments[1:])
    return handle_execute(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
