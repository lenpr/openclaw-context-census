from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.helpers import PROJECT_ROOT, load_content_census_module, write_fixture_tree


ccr = load_content_census_module()


class CliTests(unittest.TestCase):
    def test_build_script_check_passes_for_generated_standalone_file(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "build_single_file.py"),
                "--check",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)

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
            self.assertIn("Duplicates", report)
            self.assertIn('id="duplicate-filter"', report)
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

    def test_cli_can_write_markdown_without_html_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = write_fixture_tree(root)
            markdown_path = root / "content-census-report.md"
            html_path = root / "content-census-report.html"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "content_census_report.py"),
                    str(workspace),
                    "--markdown",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=root,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertTrue(markdown_path.exists())
            self.assertFalse(html_path.exists())

            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("# OpenClaw Snapshot Analysis Report", markdown)
            self.assertIn("## Duplicates", markdown)
            self.assertIn("Markdown report:", completed.stdout)
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

    def test_cli_can_write_all_formats_with_default_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = write_fixture_tree(root)
            html_path = root / "content-census-report.html"
            json_path = root / "content-census-report.json"
            markdown_path = root / "content-census-report.md"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "content_census_report.py"),
                    str(workspace),
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
            self.assertIn("HTML report:", completed.stdout)
            self.assertIn("JSON report:", completed.stdout)
            self.assertIn("Markdown report:", completed.stdout)


class OutputPathSelectionTests(unittest.TestCase):
    def test_selected_output_paths_defaults_to_html_only(self) -> None:
        html_path, json_path, markdown_path = ccr._selected_output_paths(
            SimpleNamespace(
                html_path=None,
                json_path=None,
                markdown_path=None,
                all_formats=False,
            )
        )

        self.assertEqual(html_path, Path("content-census-report.html"))
        self.assertIsNone(json_path)
        self.assertIsNone(markdown_path)

    def test_selected_output_paths_share_explicit_html_stem_for_markdown(self) -> None:
        html_path, json_path, markdown_path = ccr._selected_output_paths(
            SimpleNamespace(
                html_path="reports/custom-report.html",
                json_path=None,
                markdown_path=ccr.AUTO_OUTPUT_PATH,
                all_formats=False,
            )
        )

        self.assertEqual(html_path, Path("reports/custom-report.html"))
        self.assertIsNone(json_path)
        self.assertEqual(markdown_path, Path("reports/custom-report.md"))

    def test_selected_output_paths_share_explicit_json_stem_for_all_formats(self) -> None:
        html_path, json_path, markdown_path = ccr._selected_output_paths(
            SimpleNamespace(
                html_path=None,
                json_path="reports/custom-report.json",
                markdown_path=None,
                all_formats=True,
            )
        )

        self.assertEqual(html_path, Path("reports/custom-report.html"))
        self.assertEqual(json_path, Path("reports/custom-report.json"))
        self.assertEqual(markdown_path, Path("reports/custom-report.md"))


if __name__ == "__main__":
    unittest.main()
