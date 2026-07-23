from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from cn_web_search_mcp.config import Settings
from cn_web_search_mcp.core.models import Query, StageStatus
from cn_web_search_mcp.network import HttpResponse
from cn_web_search_mcp.structured_adapters import (
    ArxivSearchAdapter,
    CrossrefSearchAdapter,
    run_structured_sources,
)


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, url, **kwargs):
        return self.responses.pop(0)


class StructuredAdapterTests(unittest.TestCase):
    def settings(self, directory: str) -> Settings:
        return Settings(data_dir=Path(directory), max_results_per_source=3)

    def test_crossref_normalizes_structured_metadata(self):
        payload = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1/example",
                        "title": ["A useful paper"],
                        "URL": "https://doi.org/10.1/example",
                        "publisher": "Example Publisher",
                        "published": {"date-parts": [[2026, 7, 20]]},
                        "abstract": "<jats:p>Direct abstract evidence.</jats:p>",
                    }
                ]
            }
        }
        response = HttpResponse(
            "https://api.crossref.org/works",
            200,
            {"content-type": "application/json; charset=utf-8"},
            json.dumps(payload).encode(),
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            adapter = CrossrefSearchAdapter(FakeClient([response]), self.settings(directory))
            result = adapter.search(Query("q1", "useful paper", ["r1"]))
        self.assertEqual(result.status, StageStatus.SUCCESS)
        self.assertEqual(result.results[0].published_at, "2026-07-20")
        self.assertEqual(result.results[0].content, "Direct abstract evidence.")

    def test_arxiv_and_crossref_fail_independently_in_batch(self):
        empty_feed = b'<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        arxiv_response = HttpResponse(
            "https://export.arxiv.org/api/query",
            200,
            {"content-type": "application/atom+xml; charset=utf-8"},
            empty_feed,
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            settings = self.settings(directory)
            adapters = [
                ArxivSearchAdapter(FakeClient([arxiv_response]), settings),
                CrossrefSearchAdapter(FakeClient([]), settings),
            ]
            execution = asyncio.run(
                run_structured_sources(adapters, [Query("q1", "paper", ["r1"])], timeout_seconds=2)
            )
        statuses = {stage.engine: stage.status for stage in execution.stages}
        self.assertEqual(statuses["arxiv_api"], StageStatus.EMPTY)
        self.assertEqual(statuses["crossref_api"], StageStatus.ERROR)


if __name__ == "__main__":
    unittest.main()
