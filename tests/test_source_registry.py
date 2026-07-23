from __future__ import annotations

import tempfile
import unittest
from importlib.resources import files
from pathlib import Path

from cn_web_search_mcp.core.knowledge.loader import load_authority_entries
from cn_web_search_mcp.core.sources import DuplicateYamlKeyError, SourceRegistry


class SourceRegistryTests(unittest.TestCase):
    def test_default_catalog_is_complete_and_equivalent_to_markdown(self):
        registry = SourceRegistry.load_default()
        markdown = files("cn_web_search_mcp").joinpath("data/authoritative-sites.md")
        legacy = load_authority_entries(str(markdown))

        migrated_sources = registry.authority_sources()
        self.assertEqual(len(legacy), len(migrated_sources))
        self.assertEqual(
            [
                (item.entity, item.category, item.keywords, item.urls)
                for item in legacy
            ],
            [
                (
                    source.legacy_entity,
                    source.legacy_category,
                    source.keywords,
                    [
                        endpoint.url
                        for endpoint in source.endpoints
                        if endpoint.method == "homepage"
                    ],
                )
                for source in migrated_sources
            ],
        )
        report = registry.full_scan_report()
        self.assertTrue(report["validation_completed"])
        self.assertEqual(report["declared_sources"], report["loaded_sources"])
        self.assertEqual(report["loaded_sources"], len(legacy) + 5)

    def test_duplicate_yaml_mapping_key_is_rejected(self):
        content = """\
version: 2
version: 3
declared_sources: 1
provenance: {}
sources: []
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.yaml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(DuplicateYamlKeyError):
                SourceRegistry.load(path)

    def test_unknown_source_has_clear_error(self):
        registry = SourceRegistry.load_default()
        with self.assertRaisesRegex(KeyError, "unknown source"):
            registry.get("does-not-exist")


if __name__ == "__main__":
    unittest.main()
