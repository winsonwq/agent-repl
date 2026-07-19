from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import psutil

from agent_repl.cli import state_dir_from
from agent_repl.security import ResourceLimits, sanitized_environment
from agent_repl.sessions import SessionStore
from agent_repl.models import SessionRecord


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SecurityTests(unittest.TestCase):
    def test_default_state_is_namespaced_outside_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "project"
            workspace.mkdir()
            with patch.dict(os.environ, {"AGENT_REPL_STATE_DIR": str(Path(temporary) / "runtime")}, clear=False):
                state = state_dir_from(Namespace(state_dir=None), workspace)
            self.assertNotEqual(state, workspace / ".agent-repl")
            self.assertEqual(state.parent, (Path(temporary) / "runtime").resolve())

    def test_state_directories_are_owner_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SessionStore(Path(temporary) / "state")
            mode = stat.S_IMODE(store.state_dir.stat().st_mode)
            self.assertEqual(mode, 0o700)
            self.assertEqual(stat.S_IMODE(store.connections_dir.stat().st_mode), 0o700)

    def test_environment_uses_allowlist(self):
        with patch.dict(
            os.environ,
            {"PATH": "/bin", "HOME": "/tmp/home", "DATABASE_PASSWORD": "secret"},
            clear=True,
        ):
            value = sanitized_environment(Path("/tmp/context.json"), "token")
        self.assertEqual(value["PATH"], "/bin")
        self.assertNotIn("DATABASE_PASSWORD", value)
        self.assertEqual(value["AGENT_REPL_PROCESS_TOKEN"], "token")

    def test_resource_limits_parse_from_environment(self):
        with patch.dict(
            os.environ,
            {"AGENT_REPL_MAX_MEMORY_MB": "1024", "AGENT_REPL_MAX_OPEN_FILES": "256"},
            clear=True,
        ):
            limits = ResourceLimits.from_environment()
        self.assertEqual(limits.memory_mb, 1024)
        self.assertEqual(limits.open_files, 256)
        self.assertIsNone(limits.cpu_seconds)

    def test_installer_dry_run_is_structured_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command = [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "install.py"),
                "--dry-run",
                "--runtime-dir",
                str(root / "runtime"),
                "--bin-dir",
                str(root / "bin"),
                "--project-dir",
                str(root / "project"),
                "--scope",
                "project",
            ]
            for _ in range(2):
                completed = subprocess.run(command, capture_output=True, text=True, check=True)
                payload = json.loads(completed.stdout)
                self.assertEqual(payload["status"], "ok")
                self.assertTrue(payload["data"]["dry_run"])

    def test_unverified_pid_is_never_signaled(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SessionStore(Path(temporary) / "state")
            connection = store.connections_dir / "fake.json"
            context = store.contexts_dir / "fake.json"
            connection.write_text("{}", encoding="utf-8")
            context.write_text("{}", encoding="utf-8")
            record = SessionRecord(
                session_id="default:py:tampered",
                logical_session="tampered",
                runtime_name="python",
                language="python",
                pid=os.getpid(),
                connection_file=str(connection),
                context_file=str(context),
                workdir=temporary,
                created_at="2026-07-19T00:00:00+00:00",
                process_create_time=psutil.Process(os.getpid()).create_time(),
                process_token="forged",
            )
            store.save(record)
            with patch.object(store, "_terminate_known_child") as terminate:
                stopped = store.stop(record.session_id)
            self.assertFalse(stopped)
            terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
