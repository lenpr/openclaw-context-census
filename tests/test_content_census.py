from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import load_content_census_module, write_fixture_tree


ccr = load_content_census_module()


class InquiryTests(unittest.TestCase):
    LEGACY_NAME = "Context" + "Mate"

    def test_build_inquiry_prompt_includes_schema_and_preview_bytes(self) -> None:
        prompt = ccr._build_inquiry_prompt(
            [
                {
                    "absolute_path": "/tmp/demo.txt",
                    "role": "workspace_file",
                    "recommendation": "review",
                    "semantic_category": "unknown",
                    "text_preview": "first line\nsecond line\nthird line",
                }
            ]
        )

        self.assertIn("Return JSON only", prompt)
        self.assertIn("cautious system administrator", prompt)
        self.assertIn('"absolute_path", "what_it_is", "why_it_exists", "authorship", "importance", "if_deleted", "recommended_action", "action_reason", "archive_note", "standardness", "evidence_basis", "confidence"', prompt)
        self.assertIn('"purge_candidate"', prompt)
        self.assertIn("preview_bytes: |", prompt)
        self.assertIn("first line", prompt)

    def test_build_inquiry_prompt_redacts_legacy_brand_mentions(self) -> None:
        prompt = ccr._build_inquiry_prompt(
            [
                {
                    "absolute_path": "/tmp/demo.txt",
                    "text_preview": f"{self.LEGACY_NAME} assessment notes",
                }
            ]
        )

        self.assertNotIn(self.LEGACY_NAME, prompt)
        self.assertIn("another tool", prompt)

    def test_trim_inquiry_preview_handles_line_and_char_limits(self) -> None:
        lines = "\n".join(f"line {index}" for index in range(1, 20))
        self.assertEqual(ccr._trim_inquiry_preview(lines, max_chars=64, max_lines=3), "line 1\nline 2\nline 3")

        chars = "x" * 60
        trimmed = ccr._trim_inquiry_preview(chars, max_chars=16, max_lines=3)
        self.assertLessEqual(len(trimmed), 16)
        self.assertTrue(trimmed.endswith("…"))

    def test_legacy_sleuth_aliases_still_point_to_inquiry_helpers(self) -> None:
        self.assertIs(ccr._build_sleuth_prompt, ccr._build_inquiry_prompt)
        self.assertIs(ccr._parse_sleuth_payload_text, ccr._parse_inquiry_payload_text)
        self.assertIs(ccr._trim_sleuth_preview, ccr._trim_inquiry_preview)
        self.assertIs(ccr._attach_openclaw_sleuth, ccr._attach_openclaw_inquiry)

    def test_request_openclaw_inquiry_batch_normalizes_response_fields(self) -> None:
        payload = {
            "result": {
                "meta": {
                    "durationMs": 42,
                    "agentMeta": {
                        "model": "openai/test",
                        "sessionId": "session-1",
                    },
                },
                "payloads": [
                    {
                        "text": json.dumps(
                            [
                                {
                                    "absolute_path": "/tmp/demo.txt",
                                    "what_it_is": "Demo file",
                                    "why_it_exists": "Created for testing.",
                                    "authorship": "likely_user_authored",
                                    "importance": "low",
                                    "if_deleted": "Little operational impact.",
                                    "recommended_action": "delete",
                                    "action_reason": "Disposable fixture.",
                                    "archive_note": "not_needed",
                                    "standardness": "local_custom",
                                    "evidence_basis": ["path", "preview"],
                                    "confidence": "high",
                                }
                            ]
                        )
                    }
                ],
            }
        }

        with mock.patch.object(ccr, "_run_openclaw_json_command", return_value=payload):
            results = ccr._request_openclaw_inquiry_batch(
                Path("/tmp/openclaw"),
                agent_id="main",
                batch=[{"absolute_path": "/tmp/demo.txt"}],
                timeout_seconds=30,
            )

        self.assertEqual(results["/tmp/demo.txt"]["recommended_action"], "purge_candidate")
        self.assertEqual(results["/tmp/demo.txt"]["evidence_basis"], ["path", "preview"])
        self.assertEqual(results["/tmp/demo.txt"]["standardness"], "local_custom")
        self.assertEqual(results["/tmp/demo.txt"]["model"], "openai/test")

    def test_sanitize_report_payload_redacts_nested_legacy_brand_mentions(self) -> None:
        payload = ccr._sanitize_report_payload(
            {
                "text_preview": f"{self.LEGACY_NAME} report",
                "entries": [{"inquiry": {"what_it_is": f"{self.LEGACY_NAME.lower()} cache"}}],
            }
        )
        payload_json = json.dumps(payload)

        self.assertNotIn(self.LEGACY_NAME, payload_json)
        self.assertNotIn(self.LEGACY_NAME.lower(), payload_json.lower())
        self.assertIn("another tool", payload_json)

    def test_attach_openclaw_inquiry_enriches_highlight_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = write_fixture_tree(Path(temp_dir))
            snapshot = ccr.build_live_snapshot(workspace)
            result = ccr.analyze_snapshots([snapshot])

            def fake_batch(_cli_path, *, agent_id, batch, timeout_seconds):
                response = {}
                for item in batch:
                    response[str(item["absolute_path"])] = {
                        "status": "ok",
                        "what_it_is": f"Investigated {Path(str(item['absolute_path'])).name}",
                        "why_it_exists": "Fixture explanation.",
                        "authorship": "likely_openclaw_subsystem",
                        "importance": "important",
                        "if_deleted": "The workflow would lose a supporting file.",
                        "recommended_action": "keep",
                        "action_reason": "The file supports normal operation.",
                        "archive_note": "not_needed",
                        "standardness": "common_convention",
                        "evidence_basis": ["path", "preview"],
                        "confidence": "medium",
                        "model": "openai-codex/test",
                        "session_id": "session-test",
                        "duration_ms": 1234,
                        "captured_at_utc": "2026-03-14T00:00:00+00:00",
                    }
                self.assertEqual(agent_id, "main")
                self.assertGreater(timeout_seconds, 0)
                return response

            with mock.patch.object(ccr, "_discover_openclaw_cli", return_value=Path("/tmp/openclaw")), \
                 mock.patch.object(ccr, "_discover_default_agent_id", return_value="main"), \
                 mock.patch.object(ccr, "_request_openclaw_inquiry_batch", side_effect=fake_batch):
                enriched = ccr._attach_openclaw_inquiry(
                    result,
                    openclaw_root=Path(snapshot.scan.openclaw_root),
                    cache_path=None,
                    batch_size=4,
                    timeout_seconds=30,
                    progress=None,
                )

            largest = enriched.highlights["largest_files"][0]
            self.assertIn("inquiry", largest)
            self.assertEqual(largest["inquiry"]["status"], "ok")
            self.assertEqual(largest["inquiry"]["recommended_action"], "keep")
            self.assertEqual(largest["inquiry"]["importance"], "important")
            self.assertEqual(enriched.highlights["inquiry_summary"]["status"], "ok")
            self.assertGreater(enriched.highlights["inquiry_summary"]["completed"], 0)

            report = ccr.render_html_report(enriched)
            self.assertIn("OpenClaw File Inquiry", report)
            self.assertIn("Inquiry files", report)
            self.assertIn("Preview Bytes", report)
            self.assertIn("If deleted:", report)
            self.assertIn("Recommended action:", report)

    def test_attach_openclaw_inquiry_tracks_progress_by_file_count(self) -> None:
        class RecordingProgress:
            def __init__(self) -> None:
                self.events: list[tuple[object, ...]] = []

            def start_count(self, label, total=None) -> None:
                self.events.append(("start_count", label, total))

            def set_label(self, label, *, force=False) -> None:
                self.events.append(("set_label", label, force))

            def tick(self) -> None:
                self.events.append(("tick",))

            def count_tick(self, increment=1, *, force=False) -> None:
                self.events.append(("count_tick", increment, force))

            def finish(self, label) -> None:
                self.events.append(("finish", label))

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = write_fixture_tree(Path(temp_dir))
            snapshot = ccr.build_live_snapshot(workspace)
            result = ccr.analyze_snapshots([snapshot])
            progress = RecordingProgress()
            target_count = len(ccr._collect_highlight_targets(result.highlights))

            def fake_batch(_cli_path, *, agent_id, batch, timeout_seconds):
                self.assertEqual(agent_id, "main")
                self.assertGreater(timeout_seconds, 0)
                return {
                    str(item["absolute_path"]): {
                        "status": "ok",
                        "what_it_is": "Fixture file",
                        "why_it_exists": "Fixture explanation.",
                        "authorship": "likely_openclaw_subsystem",
                        "importance": "important",
                        "if_deleted": "The workflow would lose a supporting file.",
                        "recommended_action": "keep",
                        "action_reason": "The file supports normal operation.",
                        "archive_note": "not_needed",
                        "standardness": "common_convention",
                        "evidence_basis": ["path"],
                        "confidence": "medium",
                    }
                    for item in batch
                }

            with mock.patch.object(ccr, "_discover_openclaw_cli", return_value=Path("/tmp/openclaw")), \
                 mock.patch.object(ccr, "_discover_default_agent_id", return_value="main"), \
                 mock.patch.object(ccr, "_request_openclaw_inquiry_batch", side_effect=fake_batch):
                ccr._attach_openclaw_inquiry(
                    result,
                    openclaw_root=Path(snapshot.scan.openclaw_root),
                    cache_path=None,
                    batch_size=10,
                    timeout_seconds=30,
                    progress=progress,
                )

            self.assertIn(("start_count", "Querying highlight files", target_count), progress.events)
            completed_by_progress = sum(
                int(event[1])
                for event in progress.events
                if event[0] == "count_tick"
            )
            self.assertEqual(completed_by_progress, target_count)
            self.assertIn(("finish", "Highlight file inquiry complete"), progress.events)


if __name__ == "__main__":
    unittest.main()
