from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class BenchmarkTests(unittest.TestCase):
    def test_token_benchmark_captures_break_even(self):
        with tempfile.TemporaryDirectory() as temporary:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "benchmarks" / "token_cost.py"),
                    "--output-dir",
                    temporary,
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(completed.stdout)["data"]
        comparisons = {row["name"]: row for row in payload["comparisons"]}
        self.assertGreater(
            comparisons["Four-step Excel commands only"]["unified_reduction_pct"],
            20,
        )
        self.assertLess(
            comparisons["Mixed workflow with 10-row JSON handoff"]["unified_reduction_pct"],
            0,
        )
        self.assertGreater(
            comparisons["Mixed workflow with 100-row JSON handoff"]["unified_reduction_pct"],
            80,
        )
        self.assertGreater(
            comparisons["Mixed workflow with 1,000-row JSON handoff"]["unified_reduction_pct"],
            95,
        )

    def test_roadmap_has_unique_multilanguage_tasks(self):
        import re

        content = (PROJECT_ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        task_ids = re.findall(r"\*\*(AR-\d+|SEC-\d+|PERF-\d+)", content)
        self.assertEqual(len(task_ids), len(set(task_ids)))
        self.assertIn("JavaScript Runtime", content)
        self.assertIn("TypeScript Runtime", content)
        self.assertIn("Definition of done for every runtime", content)


if __name__ == "__main__":
    unittest.main()
