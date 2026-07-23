from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cn_web_search_mcp.config import Settings
from cn_web_search_mcp.core.engines import EngineResponse
from cn_web_search_mcp.core.models import Query, SearchResult, StageStatus
from cn_web_search_mcp.core.sources import SourceRegistry, build_source_adapter_registry
from cn_web_search_mcp.core.sources.adapters.catalog import CatalogDiscoveryAdapter
from cn_web_search_mcp.network import HttpResponse
from cn_web_search_mcp.structured_adapters import PubMedSearchAdapter


class FakeBackend:
    name = "web_search"

    def __init__(self, response: EngineResponse):
        self.response = response
        self.queries: list[Query] = []

    def search(self, query: Query) -> EngineResponse:
        self.queries.append(query)
        return self.response


class FakeClient:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class SourceAdapterTests(unittest.TestCase):
    def settings(self, directory: str) -> Settings:
        return Settings(data_dir=Path(directory), max_results_per_source=3)

    def test_catalog_adapter_scopes_query_and_filters_foreign_domains(self):
        registry = SourceRegistry.load_default()
        source = registry.get("dongqiudi")
        response = EngineResponse(
            StageStatus.SUCCESS,
            [
                SearchResult("r1", "web_search", "q1", "match", "https://www.dongqiudi.com/article/1"),
                SearchResult("r2", "web_search", "q1", "noise", "https://example.com/noise"),
            ],
        )
        backend = FakeBackend(response)
        adapter = CatalogDiscoveryAdapter(source, backend)

        result = adapter.search(Query("q1", "世界杯赛程", ["r1"]))

        self.assertEqual(result.status, StageStatus.SUCCESS)
        self.assertEqual(len(result.results), 1)
        self.assertIn("site:dongqiudi.com", backend.queries[0].text)
        self.assertEqual(result.results[0].engine, "catalog_dongqiudi")
        self.assertEqual(result.results[0].search_channel, "catalog_source")
        self.assertTrue(adapter.discovery_endpoint_ids)
        self.assertFalse(adapter.endpoint_ids)

    def test_default_registry_covers_direct_and_discovery_adapters(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = self.settings(directory)
            sources = SourceRegistry.load_default()
            adapters = build_source_adapter_registry(settings, FakeClient(), sources)
            report = adapters.coverage().report(sources)

        self.assertEqual(report["executable_endpoint_count"], 7)
        self.assertGreater(report["discovery_endpoint_count"], 90)
        self.assertEqual(report["sources"]["nih"]["executable"], ["pubmed-eutils-api"])
        self.assertTrue(adapters.get("dongqiudi"))

    def test_pubmed_normalizes_esearch_and_esummary(self):
        search = HttpResponse(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            200,
            {"content-type": "application/json"},
            json.dumps({"esearchresult": {"idlist": ["123"]}}).encode(),
            1,
        )
        summary = HttpResponse(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            200,
            {"content-type": "application/json"},
            json.dumps(
                {
                    "result": {
                        "123": {
                            "title": "A clinical result",
                            "pubdate": "2026 Jul 21",
                            "fulljournalname": "Example Journal",
                            "authors": [{"name": "Li Q"}],
                        }
                    }
                }
            ).encode(),
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient([search, summary])
            adapter = PubMedSearchAdapter(client, self.settings(directory))
            result = adapter.search(Query("q1", "clinical result", ["r1"]))

        self.assertEqual(result.status, StageStatus.SUCCESS)
        self.assertEqual(result.results[0].url, "https://pubmed.ncbi.nlm.nih.gov/123/")
        self.assertEqual(result.results[0].published_at, "2026 Jul 21")
        self.assertIn("esummary.fcgi", client.calls[1][0])


if __name__ == "__main__":
    unittest.main()
