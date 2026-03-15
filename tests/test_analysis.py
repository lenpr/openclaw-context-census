from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REFERENCE_TIME, load_content_census_module, write_fixture_tree


ccr = load_content_census_module()


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.workspace = write_fixture_tree(Path(cls.temp_dir.name))
        snapshot = ccr.build_live_snapshot(cls.workspace)
        cls.result = ccr.analyze_snapshots(
            [snapshot],
            config=ccr.AnalysisConfig(
                archive_days=30,
                stale_days=90,
                large_file_bytes=32 * 1024,
                reference_time_utc=REFERENCE_TIME,
            ),
        )
        cls.payload = json.loads(ccr.render_json_report(cls.result))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def _entry(self, logical_path: str, *, root_type: str | None = None):
        for entry in self.result.entries:
            if entry.logical_path == logical_path and (root_type is None or entry.root_type == root_type):
                return entry
        self.fail(f"Unable to find analyzed entry for {logical_path!r}")

    def test_memory_daily_is_keep_synced(self) -> None:
        entry = self._entry("memory/2026-03-14.md", root_type="workspace")
        self.assertEqual(entry.recommendation, ccr.Recommendation.KEEP_SYNCED)
        self.assertEqual(entry.confidence, ccr.Confidence.HIGH)
        self.assertIn("ROLE_MEMORY_DAILY", entry.reason_codes)

    def test_skill_manifest_is_keep_synced(self) -> None:
        entry = self._entry("skills/find-skills/SKILL.md", root_type="workspace")
        self.assertEqual(entry.recommendation, ccr.Recommendation.KEEP_SYNCED)
        self.assertIn("ROLE_SKILL_MANIFEST", entry.reason_codes)

    def test_workspace_mirror_under_openclaw_root_is_ignored(self) -> None:
        mirror_entry = next(
            entry
            for entry in self.result.entries
            if entry.root_type == "openclaw" and entry.relative_path == "workspace/AGENTS.md"
        )
        self.assertEqual(mirror_entry.recommendation, ccr.Recommendation.IGNORE)
        self.assertIn("WORKSPACE_MIRROR", mirror_entry.reason_codes)

    def test_credentials_and_large_model_are_classified_sensibly(self) -> None:
        credentials = self._entry("credentials/openai.key", root_type="openclaw")
        model = self._entry("tools/whisper.cpp/models/ggml-base.bin", root_type="workspace")

        self.assertEqual(credentials.recommendation, ccr.Recommendation.REVIEW)
        self.assertEqual(credentials.confidence, ccr.Confidence.HIGH)
        self.assertIn("ROLE_CREDENTIALS", credentials.reason_codes)

        self.assertEqual(model.recommendation, ccr.Recommendation.ARCHIVE_CANDIDATE)
        self.assertIn("LARGE_FILE", model.reason_codes)
        self.assertIn("PATH_MODELS", model.reason_codes)

    def test_json_report_includes_reference_metadata_and_folder_overview(self) -> None:
        agents = next(
            entry
            for entry in self.payload["entries"]
            if entry["logical_path"] == "AGENTS.md" and entry["root_type"] == "workspace"
        )
        skill = next(
            entry
            for entry in self.payload["entries"]
            if entry["logical_path"] == "skills/find-skills/SKILL.md" and entry["root_type"] == "workspace"
        )
        lockfile = next(
            entry
            for entry in self.payload["entries"]
            if entry["logical_path"] == "package-lock.json" and entry["root_type"] == "workspace"
        )

        self.assertEqual(self.payload["report_version"], "0.1")
        self.assertIn("folder_overview", self.payload)
        self.assertGreater(self.payload["folder_overview"]["total_size_bytes"], 0)
        self.assertIn("cleanup_plan", self.payload)
        self.assertEqual(self.payload["cleanup_plan"]["mode"], "recommendations_only")
        self.assertTrue(self.payload["cleanup_plan"]["requires_human_review"])
        self.assertFalse(self.payload["cleanup_plan"]["destructive_actions_included"])
        self.assertEqual(agents["known_reference"]["id"], "agents_md")
        self.assertEqual(skill["skill_registry_reference"]["panel_title"], "ClawHub Skill Reference")
        self.assertEqual(lockfile["file_type_reference"]["id"], "basename_package_lock_json")

        credentials = next(
            candidate
            for candidate in self.payload["cleanup_plan"]["candidates"]
            if candidate["logical_path"] == "credentials/openai.key"
        )
        self.assertIn("sensitive_data", credentials["manual_review_reasons"])
        self.assertEqual(credentials["suggested_next_step"], "inspect_before_any_change")

    def test_html_report_contains_primary_sections_and_external_links(self) -> None:
        report = ccr.render_html_report(self.result)

        self.assertIn("Context Census Report", report)
        self.assertIn("Check First", report)
        self.assertIn("Folders &amp; Size", report)
        self.assertIn("File Explorer", report)
        self.assertIn("Evidence Guide &amp; External Links", report)
        self.assertIn("Run summary facts &amp; metadata.", report)
        self.assertNotIn('<div class="hero-panel-title">Run Summary</div>', report)
        self.assertIn("External Links", report)
        self.assertIn("OpenClaw Docs", report)
        self.assertIn("ClawHub Skills", report)
        self.assertIn('class="inquiry-info-badge"', report)
        self.assertIn('class="tooltip-shell"', report)
        self.assertIn('class="inquiry-tooltip"', report)
        self.assertIn('role="tooltip"', report)
        self.assertIn("Example response", report)
        self.assertIn('id="page-first"', report)
        self.assertIn('id="page-last"', report)
        self.assertIn('data-sort-key="size"', report)
        self.assertIn('class="catalog-toggle-chevron"', report)
        self.assertIn("&#9662;", report)
        self.assertNotIn('class="catalog-shell" open', report)
        self.assertNotIn("Load More", report)


if __name__ == "__main__":
    unittest.main()
