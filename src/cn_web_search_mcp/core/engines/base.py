"""Search adapter protocol. Host agents provide the actual tool calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..models import Query, SearchResult, StageStatus


REQUIRED_SOURCES = ("360", "sogou", "bing_rss", "web_search")


@dataclass(slots=True)
class EngineResponse:
    status: StageStatus
    results: list[SearchResult] = field(default_factory=list)
    error: str | None = None


class EngineAdapter(Protocol):
    name: str

    def search(self, query: Query) -> EngineResponse: ...


class FixtureAdapter:
    """Deterministic adapter for host-provided results and offline tests."""

    def __init__(self, name: str, responses: dict[str, EngineResponse] | None = None):
        if name not in REQUIRED_SOURCES:
            raise ValueError(f"unsupported engine: {name}")
        self.name = name
        self._responses = responses or {}

    def search(self, query: Query) -> EngineResponse:
        return self._responses.get(
            query.id,
            EngineResponse(status=StageStatus.ERROR, error="host adapter did not provide a response"),
        )
