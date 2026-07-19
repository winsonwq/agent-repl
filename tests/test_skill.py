from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL = PROJECT_ROOT / "skills" / "agent-repl" / "SKILL.md"


class SkillTests(unittest.TestCase):
    def test_skill_is_natural_language_first(self):
        content = SKILL.read_text(encoding="utf-8")
        self.assertIn("Treat the user's request as the interface", content)
        self.assertIn("Do not ask the user to configure a workspace", content)
        self.assertIn("Omit `--session`", content)
        self.assertIn("Import pandas", content)
        self.assertNotIn("Choose the target automatically", content)
        self.assertNotIn("AGENT_REPL_WORKDIR", content)

    def test_skill_has_path_independent_runner(self):
        content = SKILL.read_text(encoding="utf-8")
        runner = PROJECT_ROOT / "skills" / "agent-repl" / "scripts" / "agent-repl"
        self.assertIn("${CLAUDE_SKILL_DIR}/scripts/agent-repl", content)
        self.assertTrue(runner.is_file())
        self.assertTrue(runner.stat().st_mode & 0o111)
        completed = subprocess.run([str(runner), "doctor", "--json"], cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "ok")

    def test_skill_eval_cases_cover_trigger_and_near_miss(self):
        value = json.loads((PROJECT_ROOT / "skills" / "agent-repl" / "evals" / "evals.json").read_text())
        self.assertEqual(len(value["evals"]), 3)
        self.assertTrue(any("xlsx" in case["prompt"] for case in value["evals"]))
        self.assertTrue(any("不需要运行" in case["prompt"] for case in value["evals"]))


if __name__ == "__main__":
    unittest.main()
