"""Bounded, domain-aware concurrent content fetching."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable
from urllib.parse import urlsplit

from .config import ExecutionLimits


@dataclass(slots=True)
class FetchOutcome:
    url: str
    status: str
    value: Any = None
    error: str | None = None
    elapsed_ms: int = 0


class FetchCoordinator:
    def __init__(self, fetcher: Callable[[str], Any], limits: ExecutionLimits | None = None):
        self.fetcher = fetcher
        self.limits = limits or ExecutionLimits.from_env()
        self._global = asyncio.Semaphore(self.limits.max_fetch_concurrency)
        self._domain_semaphores: dict[str, asyncio.Semaphore] = {}
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self._last_started: dict[str, float] = {}

    @staticmethod
    def _domain(url: str) -> str:
        domain = (urlsplit(url).hostname or "").casefold()
        if not domain:
            raise ValueError(f"URL has no domain: {url}")
        return domain

    async def _respect_domain_delay(self, domain: str) -> None:
        lock = self._domain_locks.setdefault(domain, asyncio.Lock())
        async with lock:
            delay = self.limits.per_domain_delay_ms / 1000
            elapsed = perf_counter() - self._last_started.get(domain, 0.0)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
            self._last_started[domain] = perf_counter()

    async def _fetch_one(self, url: str) -> FetchOutcome:
        started = perf_counter()
        try:
            domain = self._domain(url)
        except ValueError as exc:
            return FetchOutcome(url, "error", error=str(exc))
        domain_semaphore = self._domain_semaphores.setdefault(
            domain, asyncio.Semaphore(self.limits.per_domain_concurrency)
        )
        try:
            async with self._global, domain_semaphore:
                await self._respect_domain_delay(domain)
                async def invoke():
                    if inspect.iscoroutinefunction(self.fetcher):
                        return await self.fetcher(url)
                    value = await asyncio.to_thread(self.fetcher, url)
                    if inspect.isawaitable(value):
                        value = await value
                    return value

                value = await asyncio.wait_for(
                    invoke(), timeout=self.limits.fetch_timeout_seconds
                )
        except asyncio.TimeoutError:
            return FetchOutcome(
                url,
                "timeout",
                error=f"fetch exceeded {self.limits.fetch_timeout_seconds}s",
                elapsed_ms=round((perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return FetchOutcome(
                url, "error", error=str(exc), elapsed_ms=round((perf_counter() - started) * 1000)
            )
        return FetchOutcome(
            url, "success", value=value, elapsed_ms=round((perf_counter() - started) * 1000)
        )

    async def fetch_many(self, urls: list[str]) -> list[FetchOutcome]:
        unique_urls = list(dict.fromkeys(urls))
        if len(unique_urls) > self.limits.max_fetches_per_round:
            raise ValueError(
                f"fetch limit exceeded: {len(unique_urls)} > {self.limits.max_fetches_per_round}"
            )
        return list(await asyncio.gather(*(self._fetch_one(url) for url in unique_urls)))
