from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import PROJECT_ROOT, write_fixture_tree


class CliTests(unittest.TestCase):
    def test_help_text_describes_available_output_modes(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "content_census_report.py"), "--help"],
            check=False,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("HTML, JSON, and/or Markdown content census reports", completed.stdout)
        self.assertIn("~/.openclaw/workspace", completed.stdout)
        self.assertIn("--html", completed.stdout)
        self.assertIn("--json", completed.stdout)
        self.assertIn("--markdown", completed.stdout)
        self.assertIn("--all-formats", completed.stdout)

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

    def test_cli_can_write_json_without_html_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = write_fixture_tree(root)
            json_path = root / "content-census-report.json"
            html_path = root / "content-census-report.html"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "content_census_report.py"),
                    str(workspace),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=root,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(json_path.exists())
            self.assertFalse(html_path.exists())

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("cleanup_plan", payload)
            self.assertGreater(payload["cleanup_plan"]["candidate_count"], 0)
            self.assertIn("JSON report:", completed.stdout)
            self.assertNotIn("HTML report:", completed.stdout)

    def test_cli_can_write_all_formats_with_shared_custom_stem(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = write_fixture_tree(root)
            reports_dir = root / "reports"
            html_path = reports_dir / "content-census-report.html"
            json_path = reports_dir / "content-census-report.json"
            markdown_path = reports_dir / "content-census-report.md"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "content_census_report.py"),
                    str(workspace),
                    "--html",
                    str(html_path),
                    "--all-formats",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=root,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(html_path.exists())
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())

            payload = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")
            report = html_path.read_text(encoding="utf-8")

            self.assertIn("cleanup_plan", payload)
            self.assertIn("# OpenClaw Snapshot Analysis Report", markdown)
            self.assertIn("Context Census Report", report)
            self.assertIn("HTML report:", completed.stdout)
            self.assertIn("JSON report:", completed.stdout)
            self.assertIn("Markdown report:", completed.stdout)


if __name__ == "__main__":
    unittest.main()
