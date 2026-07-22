"""Autonomous multi-round research workflow built on the existing quality Core."""

from __future__ import annotations

import asyncio
import re
from dataclasses import replace
from time import perf_counter
from typing import Any, Callable
from urllib.parse import urlsplit

from .config import Settings
from .content_fetcher import ContentFetcher
from .core.config import ExecutionLimits
from .core.engines import REQUIRED_SOURCES
from .core.models import Query, SearchResult, to_dict
from .core.orchestrator import SearchOrchestrator
from .core.planners import plan_retry_queries
from .core.processing import deduplicate_results
from .core.service import evaluate, plan
from .network import HttpClient
from .core.sources import SourceRegistry, build_source_adapter_registry
from .store import JobStore
from .structured_adapters import run_structured_sources


class ResearchCancelled(RuntimeError):
    pass


ProgressCallback = Callable[[str, int, int, int], None]
CancelCallback = Callable[[], bool]


def _query_from_dict(data: dict[str, Any]) -> Query:
    return Query(
        id=data["id"],
        text=data["text"],
        requirement_ids=list(data.get("requirement_ids", [])),
        round_number=int(data.get("round_number", 1)),
    )


def _authority_hosts(research_plan: dict[str, Any]) -> set[str]:
    hosts: set[str] = set()
    for match in research_plan["authority_scan"]["matches"]:
        for url in match.get("urls", []):
            host = (urlsplit(url).hostname or "").casefold()
            if host:
                hosts.add(host)
    return hosts


def _authority_seeds(research_plan: dict[str, Any], query: Query) -> list[SearchResult]:
    seeds: list[SearchResult] = []
    for match_index, match in enumerate(research_plan["authority_scan"]["matches"], 1):
        for url_index, url in enumerate(match.get("urls", [])[:1], 1):
            seeds.append(
                SearchResult(
                    result_id=f"authority-{match_index}-{url_index}",
                    engine="authority",
                    query_id=query.id,
                    title=match["entity"],
                    url=url,
                    publisher=(urlsplit(url).hostname or ""),
                    source_role="primary_official",
                    discovered_by=["authority_knowledge"],
                    matched_requirement_ids=list(query.requirement_ids),
                    search_channel="authority_knowledge",
                    search_backend="local-full-scan",
                )
            )
    return seeds[:3]


def _prioritize_candidates(results: list[SearchResult], limit: int) -> list[SearchResult]:
    """Put authority, requirement coverage, and source diversity inside the fetch budget."""

    unique = deduplicate_results(results)
    selected: list[SearchResult] = []
    selected_ids: set[str] = set()

    def add(item: SearchResult) -> None:
        if item.result_id not in selected_ids and len(selected) < limit:
            selected.append(item)
            selected_ids.add(item.result_id)

    for item in unique:
        if item.source_role == "primary_official" or item.engine == "authority":
            add(item)

    for query_id in dict.fromkeys(item.query_id for item in unique):
        candidate = next((item for item in unique if item.query_id == query_id and item.result_id not in selected_ids), None)
        if candidate:
            add(candidate)

    while len(selected) < limit:
        added = False
        for source in REQUIRED_SOURCES:
            candidate = next(
                (
                    item
                    for item in unique
                    if item.result_id not in selected_ids
                    and (item.engine == source or source in item.discovered_by)
                ),
                None,
            )
            if candidate:
                add(candidate)
                added = True
            if len(selected) >= limit:
                break
        if not added:
            break

    for item in unique:
        add(item)
    return selected + [item for item in unique if item.result_id not in selected_ids]


def _supports_requirement(result: SearchResult, description: str) -> bool:
    content = (result.content or "").casefold()
    if not content:
        return False
    normalized = re.sub(r"[，。！？、；：,.!?;:\s]+", " ", description.casefold())
    pieces = [
        piece
        for piece in re.split(r"(?:以及|并且|或者|还是|和|与|及|的|是|为)|\s+", normalized)
        if len(piece) >= 2
    ]
    latin_terms = re.findall(r"[a-z0-9][a-z0-9._+-]{1,}", normalized)
    if any(term in content for term in pieces + latin_terms):
        return True
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    bigrams = {chinese[index:index + 2] for index in range(max(0, len(chinese) - 1))}
    return sum(1 for term in bigrams if term in content) >= min(2, len(bigrams)) if bigrams else False


def _validate_requirement_matches(results: list[SearchResult], task: dict[str, Any]) -> None:
    descriptions = {item["id"]: item["description"] for item in task.get("requirements", [])}
    for result in results:
        result.matched_requirement_ids = [
            requirement_id
            for requirement_id in result.matched_requirement_ids
            if requirement_id in descriptions
            and _supports_requirement(result, descriptions[requirement_id])
        ]


class ResearchRunner:
    def __init__(
        self,
        settings: Settings,
        store: JobStore,
        *,
        adapters=None,
        source_adapters=None,
        fetcher=None,
    ):
        self.settings = settings
        self.store = store
        self._adapters = adapters
        self._source_adapters = source_adapters
        self._fetcher = fetcher

    def run(
        self,
        request: dict[str, Any],
        *,
        progress: ProgressCallback | None = None,
        cancelled: CancelCallback | None = None,
        artifact_prefix: str | None = None,
    ) -> dict[str, Any]:
        return asyncio.run(
            self.run_async(
                request,
                progress=progress,
                cancelled=cancelled,
                artifact_prefix=artifact_prefix,
            )
        )

    async def run_async(
        self,
        request: dict[str, Any],
        *,
        progress: ProgressCallback | None = None,
        cancelled: CancelCallback | None = None,
        artifact_prefix: str | None = None,
    ) -> dict[str, Any]:
        started = perf_counter()
        progress = progress or (lambda phase, round_number, completed, total: None)
        cancelled = cancelled or (lambda: False)

        def check_cancelled() -> None:
            if cancelled():
                raise ResearchCancelled("research job was cancelled")

        question = str(request.get("question", "")).strip()
        if not question:
            raise ValueError("question must not be empty")
        requirements = [str(value).strip() for value in request.get("requirements", []) if str(value).strip()]
        if len(requirements) > 12:
            raise ValueError("at most 12 requirements are allowed")
        max_rounds = int(request.get("max_rounds", 3))
        if not 1 <= max_rounds <= 5:
            raise ValueError("max_rounds must be between 1 and 5")
        profile = str(request.get("profile", "balanced")).casefold()
        if profile not in {"fast", "balanced", "thorough"}:
            raise ValueError("profile must be fast, balanced, or thorough")

        progress("planning", 0, 0, 0)
        research_plan = plan(question, requirements or None)
        research_plan["task"]["max_rounds"] = max_rounds
        if request.get("cutoff_at"):
            research_plan["task"]["time_requirement"] = {
                "type": "as_of",
                "cutoff": str(request["cutoff_at"]),
                "timezone": str(request.get("timezone", "Asia/Shanghai")),
            }
        authority_hosts = _authority_hosts(research_plan)
        check_cancelled()

        fetch_limit = {"fast": 6, "balanced": 12, "thorough": 20}[profile]
        runtime_settings = replace(
            self.settings,
            max_fetches_per_round=min(fetch_limit, max(self.settings.max_fetches_per_round, 1)),
        )
        client = HttpClient(runtime_settings)
        source_adapters = self._source_adapters
        if source_adapters is None and self._adapters is None:
            source_adapters = build_source_adapter_registry(
                runtime_settings,
                client,
                SourceRegistry.load_default(),
            )
        adapters = self._adapters or source_adapters.for_sources(
            ("search-360", "search-sogou", "search-bing-rss", "search-web")
        )
        limits = ExecutionLimits(
            max_query_concurrency=3,
            max_stage_concurrency=8,
            stage_timeout_seconds=runtime_settings.request_timeout_seconds + 1,
            max_fetch_concurrency=min(6, runtime_settings.max_fetches_per_round),
            fetch_timeout_seconds=runtime_settings.fetch_timeout_seconds + 1,
            per_domain_concurrency=1,
            per_domain_delay_ms=300,
            max_fetches_per_round=runtime_settings.max_fetches_per_round,
        )
        orchestrator = SearchOrchestrator(adapters, limits)
        fetcher = self._fetcher or ContentFetcher(runtime_settings, client, self.store)

        queries = [_query_from_dict(item) for item in research_plan["queries"]]
        selected_vertical_sources = {
            item["source_id"] for item in research_plan["source_routing"]["routes"]
        }
        routed_adapters = (
            source_adapters.for_sources(selected_vertical_sources)
            if source_adapters is not None
            else []
        )
        all_stages = []
        routed_stages = []
        all_results: list[SearchResult] = []
        final_pack = None

        for round_number in range(1, max_rounds + 1):
            check_cancelled()
            total_stages = len(queries) * (4 + len(routed_adapters))
            progress("searching", round_number, 0, total_stages)
            execution = await orchestrator.run_round_async(queries, round_number)
            all_stages.extend(execution.stages)
            routed_execution = await run_structured_sources(
                routed_adapters,
                queries,
                timeout_seconds=runtime_settings.request_timeout_seconds + 1,
            )
            routed_stages.extend(routed_execution.stages)
            progress("searching", round_number, total_stages, total_stages)
            check_cancelled()

            candidates = [*execution.results, *routed_execution.results]
            if round_number == 1 and queries:
                candidates = _authority_seeds(research_plan, queries[0]) + candidates
            candidates = _prioritize_candidates(candidates, runtime_settings.max_fetches_per_round)
            progress("fetching", round_number, 0, min(len(candidates), runtime_settings.max_fetches_per_round))
            enriched = await fetcher.enrich_results(candidates, authority_hosts=authority_hosts)
            _validate_requirement_matches(enriched, research_plan["task"])
            all_results.extend(enriched)
            progress("fetching", round_number, min(len(candidates), runtime_settings.max_fetches_per_round), min(len(candidates), runtime_settings.max_fetches_per_round))
            check_cancelled()

            payload = {
                "task": research_plan["task"],
                "round_number": round_number,
                "stages": [to_dict(item) for item in all_stages],
                "results": [to_dict(item) for item in all_results],
                "conflicts": [],
            }
            progress("evaluating", round_number, 0, 1)
            final_pack = evaluate(payload)
            progress("evaluating", round_number, 1, 1)
            if artifact_prefix:
                self.store.save_artifact(artifact_prefix, f"round-{round_number}-input.json", payload)
                self.store.save_artifact(artifact_prefix, f"round-{round_number}-evidence.json", to_dict(final_pack))
            if final_pack.status in {"sufficient", "unresolvable"}:
                break
            queries = plan_retry_queries(final_pack.task, final_pack.quality)
            if not queries:
                break

        if final_pack is None:
            raise RuntimeError("research completed without an evidence pack")
        pack_data = to_dict(final_pack)
        public_status = "completed" if final_pack.status == "sufficient" else "unresolvable"
        facts = [
            {
                "requirement_id": item.requirement_id,
                "claim": item.claim,
                "evidence_text": item.evidence_text,
                "url": item.url,
                "publisher": item.publisher,
                "source_role": item.source_role,
                "published_at": item.published_at,
                "observed_at": item.observed_at,
                "forecast_valid_at": item.forecast_valid_at,
                "confidence": item.confidence,
            }
            for item in final_pack.evidence
        ]
        result = {
            "status": public_status,
            "question": final_pack.task.question,
            "quality": to_dict(final_pack.quality),
            "answer_context": {
                "facts": facts,
                "conflicts": final_pack.conflicts,
                "unresolved": final_pack.unresolved,
                "instruction": "Answer only from these facts; cite each material claim with its URL.",
            },
            "evidence": facts,
            "unresolved": final_pack.unresolved,
            "conflicts": final_pack.conflicts,
            "trace_summary": {
                "rounds": final_pack.quality.round_number,
                "source_attempts": len(all_stages),
                "raw_results": len(all_results),
                "authority_entries_scanned": research_plan["authority_scan"]["scanned_entries"],
                "authority_scan_completed": research_plan["authority_scan"]["completed"],
                "catalog_sources_loaded": research_plan["source_catalog"]["loaded_sources"],
                "routed_source_attempts": len(routed_stages),
                "routed_sources": sorted({item.engine for item in routed_stages}),
                "structured_source_attempts": len(
                    [item for item in routed_stages if item.engine.endswith("_api")]
                ),
                "structured_sources": sorted(
                    {
                        item.engine
                        for item in routed_stages
                        if item.engine.endswith("_api")
                    }
                ),
                "elapsed_ms": round((perf_counter() - started) * 1000),
            },
        }
        if artifact_prefix:
            self.store.save_artifact(artifact_prefix, "final-evidence.json", pack_data)
            self.store.save_artifact(artifact_prefix, "result.json", result)
        return result
