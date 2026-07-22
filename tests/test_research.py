from __future__ import annotations

import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from cn_web_search_mcp.config import Settings
from cn_web_search_mcp.core.engines import EngineResponse, REQUIRED_SOURCES
from cn_web_search_mcp.core.models import SearchResult, StageStatus
from cn_web_search_mcp.core.sources import SourceAdapterRegistry, SourceRegistry
from cn_web_search_mcp.core.sources.adapters.catalog import CatalogDiscoveryAdapter
from cn_web_search_mcp.jobs import JobService
from cn_web_search_mcp.research import ResearchRunner
from cn_web_search_mcp.store import JobStore


class FakeAdapter:
    def __init__(self, name: str, calls: list[tuple[str, str]], status=StageStatus.SUCCESS):
        self.name = name
        self.calls = calls
        self.status = status

    def search(self, query):
        self.calls.append((self.name, query.id))
        if self.status is not StageStatus.SUCCESS:
            return EngineResponse(self.status, error="fixture failure")
        index = REQUIRED_SOURCES.index(self.name)
        return EngineResponse(
            StageStatus.SUCCESS,
            [
                SearchResult(
                    result_id=f"{self.name}-{query.id}",
                    engine=self.name,
                    query_id=query.id,
                    title=f"官方资料 {self.name}",
                    url=f"https://source{index}.gov.cn/{query.id}",
                    snippet=f"{query.text} 的直接资料",
                    published_at="2026-07-16T10:00:00+08:00",
                    discovered_by=[self.name],
                    matched_requirement_ids=list(query.requirement_ids),
                )
            ],
        )


class FakeFetcher:
    async def enrich_results(self, results, *, authority_hosts=None):
        enriched = []
        for result in results:
            host = result.url.split("/", 3)[2]
            enriched.append(
                replace(
                    result,
                    content=f"完整正文：{result.snippet or result.title}。这是能够支持问题的信息。",
                    content_status="fetched",
                    publisher=host,
                    source_role="primary_official",
                    published_at=result.published_at or "2026-07-16T09:00:00+08:00",
                    fetch_engine="fixture",
                    fetch_status_code=200,
                )
            )
        return enriched


class FakeWebBackend:
    name = "web_search"

    def __init__(self):
        self.queries = []

    def search(self, query):
        self.queries.append(query.text)
        return EngineResponse(
            StageStatus.SUCCESS,
            [
                SearchResult(
                    result_id="vertical-result",
                    engine=self.name,
                    query_id=query.id,
                    title="世界杯官方赛程整理",
                    url="https://www.dongqiudi.com/article/123",
                    snippet="世界杯赛程信息",
                    matched_requirement_ids=list(query.requirement_ids),
                )
            ],
        )


class FakeJobRunner:
    def run(self, request, *, progress, cancelled, artifact_prefix):
        progress("searching", 1, 4, 4)
        if cancelled():
            raise RuntimeError("cancelled")
        return {"status": "completed", "question": request["question"], "evidence": []}


class ResearchTests(unittest.TestCase):
    def settings(self, root: Path) -> Settings:
        return Settings(
            data_dir=root,
            request_timeout_seconds=0.5,
            fetch_timeout_seconds=0.5,
            max_fetches_per_round=8,
        )

    def test_autonomous_runner_completes_all_four_sources_and_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.settings(root)
            store = JobStore(root / "jobs.sqlite3", root / "artifacts")
            calls = []
            adapters = [FakeAdapter(name, calls) for name in REQUIRED_SOURCES]
            runner = ResearchRunner(settings, store, adapters=adapters, fetcher=FakeFetcher())

            result = runner.run(
                {
                    "question": "截至北京时间2026-07-16 12:00，查询世界杯赛程",
                    "requirements": ["剩余赛程和北京时间"],
                    "max_rounds": 3,
                },
                artifact_prefix="job-one",
            )

            self.assertEqual("completed", result["status"])
            self.assertGreaterEqual(result["quality"]["total_score"], 85)
            self.assertEqual(set(REQUIRED_SOURCES), {name for name, query_id in calls if query_id == "q1"})
            self.assertTrue(result["trace_summary"]["authority_scan_completed"])
            self.assertTrue((root / "artifacts" / "job-one" / "final-evidence.json").exists())

    def test_failed_sources_still_finish_at_max_rounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.settings(root)
            store = JobStore(root / "jobs.sqlite3", root / "artifacts")
            calls = []
            adapters = [FakeAdapter(name, calls, StageStatus.BLOCKED) for name in REQUIRED_SOURCES]
            runner = ResearchRunner(settings, store, adapters=adapters, fetcher=FakeFetcher())

            result = runner.run({"question": "测试搜索失败", "max_rounds": 2})

            self.assertEqual("unresolvable", result["status"])
            self.assertEqual(2, result["trace_summary"]["rounds"])
            self.assertEqual(8, len(calls))

    def test_intent_route_executes_catalog_source_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.settings(root)
            store = JobStore(root / "jobs.sqlite3", root / "artifacts")
            calls = []
            mandatory = [FakeAdapter(name, calls) for name in REQUIRED_SOURCES]
            sources = SourceRegistry.load_default()
            source_adapters = SourceAdapterRegistry(sources)
            backend = FakeWebBackend()
            source_adapters.register(
                CatalogDiscoveryAdapter(sources.get("dongqiudi"), backend)
            )
            runner = ResearchRunner(
                settings,
                store,
                adapters=mandatory,
                source_adapters=source_adapters,
                fetcher=FakeFetcher(),
            )

            result = runner.run(
                {
                    "question": "查询世界杯赛程",
                    "requirements": ["世界杯赛程"],
                    "max_rounds": 1,
                }
            )

            self.assertTrue(backend.queries)
            self.assertIn("site:dongqiudi.com", backend.queries[0])
            self.assertIn("catalog_dongqiudi", result["trace_summary"]["routed_sources"])

    def test_job_service_runs_in_background_and_persists_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = self.settings(root)
            store = JobStore(root / "jobs.sqlite3", root / "artifacts")
            service = JobService(settings, store=store, runner=FakeJobRunner())
            try:
                started = service.start({"question": "后台任务测试"})
                deadline = time.time() + 2
                status = service.status(started["job_id"])
                while status["status"] not in {"completed", "failed"} and time.time() < deadline:
                    time.sleep(0.01)
                    status = service.status(started["job_id"])
                self.assertEqual("completed", status["status"])
                self.assertEqual("后台任务测试", service.result(started["job_id"])["result"]["question"])
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
