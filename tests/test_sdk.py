from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from agent_repl_sdk.context import RuntimeContext


class RuntimeSdkTests(unittest.TestCase):
    def test_paths_artifacts_and_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = {name: str(root / name) for name in ("inputs", "working", "outputs", "artifacts", "temp")}
            context = RuntimeContext(
                {
                    "task_id": "test",
                    "session_id": "test:default",
                    "runtime": "python",
                    "language": "python",
                    "network_enabled": False,
                    "paths": paths,
                    "capabilities": ["python", "artifacts"],
                    "events_file": str(root / "events.jsonl"),
                }
            )
            input_file = Path(paths["inputs"]) / "input.txt"
            input_file.parent.mkdir(parents=True, exist_ok=True)
            input_file.write_text("hello", encoding="utf-8")

            source = context.inputs.get("input.txt")
            working = context.working.copy_from(source)
            published = context.artifacts.publish_file(working.path)

            self.assertEqual(Path(published["path"]).read_text(encoding="utf-8"), "hello")
            self.assertTrue(context.capabilities.has("python"))
            self.assertEqual(context.runtime, "python")
            self.assertEqual(context.profile, "python")
            events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
            self.assertIn("artifact_published", [event["type"] for event in events])

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            from agent_repl_sdk.context import EventEmitter, PathArea

            area = PathArea(root / "inputs", EventEmitter(None), "inputs")
            with self.assertRaises(ValueError):
                area.path("../escape.txt")


if __name__ == "__main__":
    unittest.main()
