from __future__ import annotations

import unittest

from agent_repl.profiles import parse_target


class ProfileTests(unittest.TestCase):
    def test_explicit_session(self):
        profile, session = parse_target("data@experiment-a", "default")
        self.assertEqual(profile.name, "python-data")
        self.assertEqual(session, "experiment-a")

    def test_default_session(self):
        profile, session = parse_target("excel", "task-1")
        self.assertEqual(profile.name, "python-excel")
        self.assertEqual(session, "task-1")

    def test_unknown_runtime(self):
        with self.assertRaises(ValueError):
            parse_target("ruby", "default")


if __name__ == "__main__":
    unittest.main()
