from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import PROJECT_ROOT, write_fixture_tree


class CliTests(unittest.TestCase):
    def test_help_text_describes_standalone_html_report(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "content_census_report.py"), "--help"],
            check=False,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("standalone HTML content census report", completed.stdout)
        self.assertIn("~/.openclaw/workspace", completed.stdout)
        self.assertIn("--html", completed.stdout)

    def test_cli_writes_html_report_and_shows_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = write_fixture_tree(root)
            html_path = root / "content-census-report.html"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "content_census_report.py"),
                    str(workspace),
                    "--html",
                    str(html_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(html_path.exists())
            report = html_path.read_text(encoding="utf-8")

            self.assertIn("Context Census Report", report)
            self.assertIn("File Explorer", report)
            self.assertIn("HTML report:", completed.stdout)
            self.assertIn("Counting paths", completed.stderr)
            self.assertIn("Scanning filesystem", completed.stderr)
            self.assertIn("Writing report", completed.stderr)


if __name__ == "__main__":
    unittest.main()
