#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_SOURCE = PROJECT_ROOT / "skills" / "agent-repl"


def run(command: list[str], dry_run: bool) -> None:
    print("+ " + " ".join(command), file=sys.stderr)
    if not dry_run:
        subprocess.run(command, check=True, stdout=sys.stderr, stderr=sys.stderr)


def replace_link(source: Path, destination: Path, dry_run: bool) -> None:
    if dry_run:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".new")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(source)
    temporary.replace(destination)


def copy_skill(destination: Path, runtime_executable: Path, dry_run: bool) -> None:
    if dry_run:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".new")
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(SKILL_SOURCE, temporary)
    runner = temporary / "scripts" / "agent-repl"
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nexec "
        + json.dumps(str(runtime_executable))
        + ' "$@"\n',
        encoding="utf-8",
    )
    runner.chmod(0o755)
    if destination.exists():
        shutil.rmtree(destination)
    temporary.replace(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Agent REPL runtime and Agent Skill in one idempotent command.")
    parser.add_argument("--agent", choices=("claude", "codex", "both", "none"), default="claude")
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--runtime-dir", type=Path, default=Path.home() / ".local" / "share" / "agent-repl")
    parser.add_argument("--bin-dir", type=Path, default=Path.home() / ".local" / "bin")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runtime_dir = args.runtime_dir.expanduser().resolve()
    virtualenv = runtime_dir / "venv"
    if not virtualenv.exists():
        run([args.python, "-m", "venv", str(virtualenv)], args.dry_run)
    python = virtualenv / "bin" / "python"
    run([str(python), "-m", "pip", "install", "--quiet", "--upgrade", f"{PROJECT_ROOT}[all]"], args.dry_run)

    launcher = args.bin_dir.expanduser().resolve() / "agent-repl"
    replace_link(virtualenv / "bin" / "agent-repl", launcher, args.dry_run)

    skill_destinations: list[Path] = []
    if args.agent in {"claude", "both"}:
        root = args.project_dir / ".claude" if args.scope == "project" else Path.home() / ".claude"
        skill_destinations.append(root / "skills" / "agent-repl")
    if args.agent in {"codex", "both"}:
        root = args.project_dir / ".codex" if args.scope == "project" else Path.home() / ".codex"
        skill_destinations.append(root / "skills" / "agent-repl")
    for destination in skill_destinations:
        copy_skill(destination.expanduser().resolve(), virtualenv / "bin" / "agent-repl", args.dry_run)

    on_path = str(launcher.parent) in os.environ.get("PATH", "").split(os.pathsep)
    payload = {
        "status": "ok",
        "data": {
            "runtime": str(runtime_dir),
            "launcher": str(launcher),
            "skills": [str(path.expanduser().resolve()) for path in skill_destinations],
            "on_path": on_path,
            "agent_ready": bool(skill_destinations),
            "next_command": (
                "Start the Agent and describe the task; the installed Skill has a self-contained runner"
                if skill_destinations
                else ("agent-repl doctor --json" if on_path else f"export PATH=\"{launcher.parent}:$PATH\"")
            ),
            "dry_run": args.dry_run,
        },
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
