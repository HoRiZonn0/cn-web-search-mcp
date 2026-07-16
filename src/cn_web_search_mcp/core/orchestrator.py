"""Execute every query against all mandatory sources with bounded concurrency."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from time import perf_counter

from .engines import REQUIRED_SOURCES, EngineAdapter
from .config import ExecutionLimits
from .models import Query, SearchResult, StageRecord, StageStatus


@dataclass(slots=True)
class RoundExecution:
    round_number: int
    required_query_ids: list[str] = field(default_factory=list)
    stages: list[StageRecord] = field(default_factory=list)
    results: list[SearchResult] = field(default_factory=list)

    @property
    def source_set_completed(self) -> bool:
        observed = [(stage.engine, stage.query_id) for stage in self.stages]
        required = {
            (source, query_id)
            for source in REQUIRED_SOURCES
            for query_id in self.required_query_ids
        }
        return bool(self.required_query_ids) and len(observed) == len(required) and set(observed) == required and all(
            stage.status is not StageStatus.SKIPPED for stage in self.stages
        )


class SearchOrchestrator:
    def __init__(self, adapters: list[EngineAdapter], limits: ExecutionLimits | None = None):
        mapped = {adapter.name: adapter for adapter in adapters}
        missing = [name for name in REQUIRED_SOURCES if name not in mapped]
        if missing:
            raise ValueError(f"missing mandatory adapters: {', '.join(missing)}")
        self._adapters = [mapped[name] for name in REQUIRED_SOURCES]
        self.limits = limits or ExecutionLimits.from_env()

    @staticmethod
    def _record(adapter_name, query, response_status, results, error, started) -> tuple[StageRecord, list[SearchResult]]:
        elapsed_ms = round((perf_counter() - started) * 1000)
        for result in results:
            if adapter_name not in result.discovered_by:
                result.discovered_by.append(adapter_name)
        return (
            StageRecord(
                engine=adapter_name,
                status=response_status,
                query_id=query.id,
                result_count=len(results),
                elapsed_ms=elapsed_ms,
                error=error,
            ),
            results,
        )

    def run_round(self, queries: list[Query], round_number: int) -> RoundExecution:
        """Run the complete source set concurrently from synchronous callers."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.run_round_async(queries, round_number))
        raise RuntimeError("run_round cannot be called inside an event loop; await run_round_async instead")

    async def _run_stage(self, adapter, query, stage_semaphore):
        started = perf_counter()
        try:
            async with stage_semaphore:
                async def invoke():
                    if inspect.iscoroutinefunction(adapter.search):
                        response = await adapter.search(query)
                    else:
                        response = await asyncio.to_thread(adapter.search, query)
                    if inspect.isawaitable(response):
                        response = await response
                    return response

                response = await asyncio.wait_for(
                    invoke(), timeout=self.limits.stage_timeout_seconds
                )
        except (asyncio.TimeoutError, TimeoutError) as exc:
            return self._record(adapter.name, query, StageStatus.TIMEOUT, [], str(exc), started)
        except Exception as exc:
            return self._record(adapter.name, query, StageStatus.ERROR, [], str(exc), started)
        return self._record(
            adapter.name, query, response.status, response.results, response.error, started
        )

    async def run_round_async(self, queries: list[Query], round_number: int) -> RoundExecution:
        """Run bounded query groups; every group executes all four sources concurrently."""

        execution = RoundExecution(
            round_number=round_number,
            required_query_ids=[query.id for query in queries],
        )
        query_semaphore = asyncio.Semaphore(self.limits.max_query_concurrency)
        stage_semaphore = asyncio.Semaphore(self.limits.max_stage_concurrency)

        async def run_query(query):
            async with query_semaphore:
                return await asyncio.gather(
                    *(self._run_stage(adapter, query, stage_semaphore) for adapter in self._adapters)
                )

        grouped = await asyncio.gather(*(run_query(query) for query in queries))
        for query_stages in grouped:
            for stage, results in query_stages:
                execution.stages.append(stage)
                execution.results.extend(results)
        return execution
