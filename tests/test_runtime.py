from __future__ import annotations

import unittest
from pathlib import Path

from agent_repl import __version__
from agent_repl.runtime import RUNTIME, legacy_prelude, parse_legacy_target


class RuntimeTests(unittest.TestCase):
    def test_runtime_is_python(self):
        self.assertEqual(RUNTIME.name, "python")
        self.assertEqual(RUNTIME.bootstrap, "from agent_repl_sdk import ctx")

    def test_package_version_matches_project(self):
        pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{__version__}"', pyproject)

    def test_legacy_alias_session_is_parsed(self):
        self.assertEqual(parse_legacy_target("data@experiment-a"), ("data", "experiment-a"))

    def test_non_legacy_value_is_code(self):
        self.assertIsNone(parse_legacy_target("answer = 42"))

    def test_legacy_imports_are_compatibility_preludes(self):
        self.assertIn("pandas", legacy_prelude("data"))
        self.assertIn("agent_repl_excel", legacy_prelude("excel"))
        self.assertEqual(legacy_prelude("py"), "")


if __name__ == "__main__":
    unittest.main()
