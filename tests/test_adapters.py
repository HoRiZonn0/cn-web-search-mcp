from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cn_web_search_mcp.config import Settings
from cn_web_search_mcp.content_fetcher import ContentFetcher
from cn_web_search_mcp.core.models import Query, SearchResult, StageStatus
from cn_web_search_mcp.network import HttpResponse, UnsafeUrlError, validate_public_url
from cn_web_search_mcp.search_adapters import BingRssAdapter, WebSearchAdapter, register_search_adapter_coverage
from cn_web_search_mcp.core.sources import RuntimeCoverageRegistry, SourceRegistry
from cn_web_search_mcp.store import JobStore


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)

    def post_json(self, url, payload, **kwargs):
        self.calls.append((url, {**kwargs, "payload": payload}))
        return self.responses.pop(0)


class AdapterTests(unittest.TestCase):
    def test_mandatory_search_adapters_are_reported_as_executable(self):
        registry = SourceRegistry.load_default()
        coverage = RuntimeCoverageRegistry()
        register_search_adapter_coverage(coverage)
        report = coverage.report(registry)
        self.assertEqual(report["executable_endpoint_count"], 4)
        for source_id in ("search-360", "search-sogou", "search-bing-rss", "search-web"):
            self.assertEqual(len(report["sources"][source_id]["executable"]), 1)

    def settings(self, root: Path, **changes):
        values = {"data_dir": root, **changes}
        return Settings(**values)

    def test_bing_rss_returns_normalized_result(self):
        xml = b"""<?xml version='1.0'?><rss><channel><item><title>Example</title><link>https://example.com/a</link><description>Fact</description><pubDate>Wed, 15 Jul 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
        response = HttpResponse("https://cn.bing.com/search", 200, {"content-type": "application/rss+xml; charset=utf-8"}, xml, 1)
        with tempfile.TemporaryDirectory() as directory:
            adapter = BingRssAdapter(FakeClient([response]), self.settings(Path(directory)))
            result = adapter.search(Query("q1", "test", ["r1"]))
        self.assertEqual(StageStatus.SUCCESS, result.status)
        self.assertEqual("bing", result.results[0].upstream_engine)
        self.assertIn("2026-07-15", result.results[0].published_at)

    def test_searxng_records_upstream_engines(self):
        body = b'{"results":[{"title":"A","url":"https://example.com/a","content":"fact","engines":["bing","brave"]}]}'
        response = HttpResponse("http://127.0.0.1:8080/search", 200, {"content-type": "application/json"}, body, 1)
        with tempfile.TemporaryDirectory() as directory:
            settings = self.settings(
                Path(directory),
                searxng_endpoint="http://127.0.0.1:8080",
                web_search_backend="searxng",
            )
            client = FakeClient([response])
            result = WebSearchAdapter(client, settings).search(Query("q1", "test", ["r1"]))
        self.assertEqual(StageStatus.SUCCESS, result.status)
        self.assertEqual("bing,brave", result.results[0].upstream_engine)
        self.assertTrue(client.calls[0][1]["trusted_network"])

    def test_content_fetcher_extracts_text_and_date(self):
        html = b"<html><head><title>Page</title><meta property='article:published_time' content='2026-07-16T08:00:00+08:00'></head><body><nav>menu</nav><main><h1>Heading</h1><p>Useful factual content that is deliberately longer than eighty characters for validation and evidence extraction.</p></main></body></html>"
        response = HttpResponse("https://example.com/a", 200, {"content-type": "text/html; charset=utf-8"}, html, 1)
        with tempfile.TemporaryDirectory() as directory:
            fetcher = ContentFetcher(self.settings(Path(directory)), FakeClient([response]))
            document = fetcher.fetch_one("https://example.com/a")
        self.assertEqual("success", document.status)
        self.assertNotIn("menu", document.content)
        self.assertEqual("2026-07-16T08:00:00+08:00", document.published_at)

    def test_firecrawl_fallback_and_domain_health(self):
        blocked = HttpResponse("https://example.com/a", 403, {"content-type": "text/html"}, b"access denied", 5)
        markdown = "# Page\n\n" + ("Useful evidence from a rendered page. " * 5)
        firecrawl_body = json.dumps(
            {
                "success": True,
                "data": {
                    "markdown": markdown,
                    "metadata": {
                        "sourceURL": "https://example.com/a",
                        "statusCode": 200,
                        "title": "Rendered Page",
                        "publishedTime": "2026-07-16T08:00:00+08:00"
                    }
                }
            }
        ).encode()
        rendered = HttpResponse("http://127.0.0.1:3002/v2/scrape", 200, {"content-type": "application/json"}, firecrawl_body, 10)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.settings(root, firecrawl_endpoint="http://127.0.0.1:3002")
            store = JobStore(root / "jobs.sqlite3", root / "artifacts")
            fetcher = ContentFetcher(settings, FakeClient([blocked, rendered]), store)
            document = fetcher.fetch_one("https://example.com/a")
            health = store.domain_health_get("example.com")
        self.assertEqual("success", document.status)
        self.assertEqual("firecrawl", document.engine)
        self.assertEqual(1, health["successes"])
        self.assertEqual(1, health["blocked"])
        self.assertEqual("Rendered Page", document.title)

    def test_private_targets_are_rejected(self):
        with self.assertRaises(UnsafeUrlError):
            validate_public_url("http://127.0.0.1/admin")


if __name__ == "__main__":
    unittest.main()
