from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from tests.helpers import REFERENCE_TIME, load_content_census_module, write_fixture_tree


ccr = load_content_census_module()


def _write_exact_duplicate_fixture_files(workspace: Path) -> tuple[Path, Path]:
    duplicate_dir = workspace / "duplicates"
    duplicate_dir.mkdir(parents=True, exist_ok=True)
    content = "duplicate session output\n"
    duplicate_paths = (
        duplicate_dir / "session-copy-a.log",
        duplicate_dir / "session-copy-b.log",
    )
    timestamp = datetime(2026, 1, 10, tzinfo=UTC).timestamp()
    for path in duplicate_paths:
        path.write_text(content, encoding="utf-8")
        os.utime(path, (timestamp, timestamp))
    return duplicate_paths


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

    def test_workspace_file_is_not_marked_duplicate_only_because_of_workspace_mirror(self) -> None:
        agents = self._entry("AGENTS.md", root_type="workspace")
        self.assertNotIn("DUPLICATE_HASH", agents.reason_codes)
        self.assertEqual(self.payload["summary"]["duplicate_file_group_count"], 0)

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
        self.assertIn("duplicates", self.payload)
        self.assertIn("cleanup_plan", self.payload)
        self.assertIn("agent_support", self.payload)
        self.assertEqual(self.payload["cleanup_plan"]["mode"], "recommendations_only")
        self.assertTrue(self.payload["cleanup_plan"]["requires_human_review"])
        self.assertFalse(self.payload["cleanup_plan"]["destructive_actions_included"])
        self.assertEqual(self.payload["summary"]["duplicate_file_group_count"], 0)
        self.assertEqual(self.payload["summary"]["duplicate_reclaimable_bytes"], 0)
        self.assertEqual(self.payload["duplicates"]["group_count"], 0)
        self.assertEqual(self.payload["duplicates"]["groups"], [])
        self.assertEqual(self.payload["agent_support"]["format_version"], 1)
        self.assertIn("review_batches", self.payload["cleanup_plan"])
        self.assertTrue(self.payload["cleanup_plan"]["review_batches"])
        self.assertTrue(agents["entry_id"].startswith("entry_"))
        self.assertFalse(agents["duplicate_context"]["is_duplicate"])
        self.assertIsNone(agents["duplicate_context"]["group_id"])
        self.assertEqual(agents["folder_context"]["folder_path"], ".")
        self.assertGreaterEqual(agents["folder_context"]["entry_count"], 1)
        self.assertEqual(agents["known_reference"]["id"], "agents_md")
        self.assertEqual(skill["skill_registry_reference"]["panel_title"], "ClawHub Skill Reference")
        self.assertEqual(lockfile["file_type_reference"]["id"], "basename_package_lock_json")

        credentials = next(
            candidate
            for candidate in self.payload["cleanup_plan"]["candidates"]
            if candidate["logical_path"] == "credentials/openai.key"
        )
        self.assertTrue(credentials["entry_id"].startswith("entry_"))
        self.assertIn("sensitive_data", credentials["manual_review_reasons"])
        self.assertEqual(credentials["suggested_next_step"], "inspect_before_any_change")
        self.assertFalse(credentials["duplicate_context"]["is_duplicate"])
        self.assertIn("review_packet", credentials)
        self.assertIn("verify_before_change", credentials["review_packet"])
        self.assertIn("safe_alternatives", credentials["review_packet"])
        self.assertIn("related_paths", credentials["review_packet"])

    def test_cleanup_plan_is_ranked_and_non_destructive(self) -> None:
        cleanup_plan = self.payload["cleanup_plan"]
        candidates = cleanup_plan["candidates"]

        self.assertEqual(
            [candidate["review_rank"] for candidate in candidates],
            list(range(1, len(candidates) + 1)),
        )
        self.assertTrue(all(candidate["requires_human_review"] for candidate in candidates))

        order = {
            recommendation: index
            for index, recommendation in enumerate(cleanup_plan["recommended_review_order"])
        }
        recommendation_indexes = [order[candidate["recommendation"]] for candidate in candidates]
        self.assertEqual(recommendation_indexes, sorted(recommendation_indexes))

        package_lock_index = next(
            index
            for index, candidate in enumerate(candidates)
            if candidate["logical_path"] == "package-lock.json"
        )
        memory_index = next(
            index
            for index, candidate in enumerate(candidates)
            if candidate["logical_path"] == "memory/2026-03-14.md"
        )
        self.assertLess(package_lock_index, memory_index)

        keep_synced_entry = next(
            candidate
            for candidate in candidates
            if candidate["logical_path"] == "AGENTS.md"
        )
        first_batch = cleanup_plan["review_batches"][0]
        self.assertEqual(first_batch["batch_number"], 1)
        self.assertEqual(first_batch["start_review_rank"], 1)
        self.assertGreaterEqual(first_batch["end_review_rank"], first_batch["start_review_rank"])
        self.assertIn(candidates[0]["entry_id"], first_batch["candidate_entry_ids"])
        self.assertEqual(keep_synced_entry["suggested_next_step"], "leave_in_place")
        self.assertEqual(keep_synced_entry["manual_review_reasons"], [])
        self.assertEqual(
            keep_synced_entry["review_packet"]["safe_alternatives"],
            ["leave_in_place"],
        )

    def test_html_report_contains_primary_sections_and_external_links(self) -> None:
        report = ccr.render_html_report(self.result)

        self.assertIn("Context Census Report", report)
        self.assertIn("Check First", report)
        self.assertIn("Duplicates", report)
        self.assertIn("Folders &amp; Size", report)
        self.assertIn("File Explorer", report)
        self.assertIn('id="duplicate-filter"', report)
        self.assertIn("Duplicates Only", report)
        self.assertIn("full duplicate file list", report)
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

    def test_markdown_report_includes_duplicates_empty_state(self) -> None:
        report = ccr.render_markdown_report(self.result)

        self.assertIn("## Duplicates", report)
        self.assertIn("No exact duplicate file groups were identified.", report)

    def test_duplicate_finder_groups_exact_duplicate_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = write_fixture_tree(Path(temp_dir))
            duplicate_paths = _write_exact_duplicate_fixture_files(workspace)
            snapshot = ccr.build_live_snapshot(workspace)
            result = ccr.analyze_snapshots(
                [snapshot],
                config=ccr.AnalysisConfig(
                    archive_days=30,
                    stale_days=90,
                    large_file_bytes=32 * 1024,
                    reference_time_utc=REFERENCE_TIME,
                ),
            )
            payload = json.loads(ccr.render_json_report(result))
            group = payload["highlights"]["duplicate_groups"][0]
            duplicate_names = {path.name for path in duplicate_paths}
            duplicate_size = duplicate_paths[0].stat().st_size

            self.assertEqual(payload["summary"]["duplicate_file_group_count"], 1)
            self.assertEqual(payload["summary"]["duplicate_file_count"], 2)
            self.assertEqual(payload["summary"]["duplicate_reclaimable_bytes"], duplicate_size)
            self.assertEqual(payload["highlights"]["duplicate_groups_summary"]["group_count"], 1)
            self.assertTrue(payload["highlights"]["duplicate_groups_summary"]["workspace_mirrors_excluded"])
            self.assertEqual(payload["duplicates"]["group_count"], 1)
            self.assertEqual(len(payload["duplicates"]["groups"]), 1)
            self.assertEqual(group["duplicate_count"], 2)
            self.assertEqual(group["reclaimable_bytes"], duplicate_size)
            self.assertEqual(
                {Path(member["path"]).name for member in group["members"]},
                duplicate_names,
            )
            self.assertTrue(all("DUPLICATE_HASH" in member["reason_codes"] for member in group["members"]))
            duplicate_inventory_group = payload["duplicates"]["groups"][0]
            self.assertTrue(duplicate_inventory_group["group_id"].startswith("dupgrp_"))
            self.assertEqual(duplicate_inventory_group["review_rank"], 1)
            self.assertEqual(len(duplicate_inventory_group["member_entry_ids"]), 2)
            self.assertEqual(
                {Path(member["path"]).name for member in duplicate_inventory_group["members"]},
                duplicate_names,
            )
            self.assertTrue(
                all(member["entry_id"].startswith("entry_") for member in duplicate_inventory_group["members"])
            )

            duplicate_entries = [
                entry
                for entry in payload["entries"]
                if (
                    entry["root_type"] == "workspace"
                    and entry["logical_path"] in {"duplicates/session-copy-a.log", "duplicates/session-copy-b.log"}
                )
            ]
            self.assertEqual(len(duplicate_entries), 2)
            self.assertEqual(
                {entry["duplicate_context"]["group_id"] for entry in duplicate_entries},
                {duplicate_inventory_group["group_id"]},
            )
            self.assertTrue(all(entry["duplicate_context"]["is_duplicate"] for entry in duplicate_entries))
            self.assertEqual(
                {entry["entry_id"] for entry in duplicate_entries},
                set(duplicate_inventory_group["member_entry_ids"]),
            )

            markdown = ccr.render_markdown_report(result)
            self.assertIn("## Duplicates", markdown)
            self.assertIn("duplicates/session-copy-a.log", markdown)
            self.assertIn("duplicates/session-copy-b.log", markdown)


if __name__ == "__main__":
    unittest.main()
