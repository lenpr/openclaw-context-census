from __future__ import annotations

import unittest

from tests.helpers import load_content_census_module


ccr = load_content_census_module()


class KnowledgeTests(unittest.TestCase):
    def test_known_file_catalog_contains_expected_source_kinds(self) -> None:
        catalog = ccr.all_file_knowledge()
        allowed_source_kinds = {"official", "third_party", "research"}

        self.assertGreaterEqual(len(catalog), 12)
        self.assertEqual(catalog["agents_md"]["id"], "agents_md")
        self.assertTrue(any(source["kind"] == "official" for source in catalog["agents_md"]["sources"]))
        self.assertTrue(any(source["kind"] == "third_party" for source in catalog["agents_md"]["sources"]))

        for entry in catalog.values():
            self.assertIn("sources", entry)
            for source in entry["sources"]:
                self.assertIn(source["kind"], allowed_source_kinds)
                self.assertTrue(str(source["url"]).startswith("https://"))

    def test_lookup_functions_cover_known_files_file_types_and_clawhub_skills(self) -> None:
        self.assertEqual(
            ccr.lookup_known_file_reference("AGENTS.md", "workspace_bootstrap_agents", "workspace")["id"],
            "agents_md",
        )
        self.assertEqual(
            ccr.lookup_known_file_reference("skills/find-skills/SKILL.md", "workspace_file", "workspace")["id"],
            "skill_manifest",
        )
        self.assertEqual(
            ccr.lookup_file_type_reference("repo/package-lock.json", ".json", "file")["id"],
            "basename_package_lock_json",
        )
        self.assertEqual(
            ccr.lookup_file_type_reference("ops/chat-icons/bot-assistant-inbox.png", ".png", "file")["id"],
            "ext_png",
        )

        skill_reference = ccr.lookup_clawhub_skill_reference("skills/find-skills/SKILL.md", "skill_manifest", "workspace")
        self.assertIsNotNone(skill_reference)
        self.assertEqual(skill_reference["panel_title"], "ClawHub Skill Reference")
        self.assertTrue(any(source["label"] == "ClawHub Skills" for source in skill_reference["sources"]))

    def test_large_embedded_indexes_are_available_offline(self) -> None:
        slug_index = ccr.all_clawhub_skill_slug_index()
        file_types = ccr.all_file_type_knowledge()

        self.assertGreaterEqual(len(slug_index), 20000)
        self.assertIn("find-skills", slug_index)
        self.assertGreaterEqual(len(file_types), 80)
        self.assertTrue(any(entry["id"] == "basename_ds_store" for entry in file_types.values()))


if __name__ == "__main__":
    unittest.main()
