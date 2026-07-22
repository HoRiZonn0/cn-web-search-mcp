"""Register runtime adapters against the validated YAML source catalog."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from ..coverage import RuntimeCoverageRegistry
from ..registry import SourceRegistry
from .base import CatalogSourceAdapter


class SourceAdapterRegistry:
    """Map source IDs to adapters and reject metadata/code mismatches early."""

    def __init__(self, sources: SourceRegistry) -> None:
        self.sources = sources
        self._adapters: dict[str, list[CatalogSourceAdapter]] = defaultdict(list)

    def register(self, adapter: CatalogSourceAdapter) -> None:
        """Register an adapter after validating its declared endpoint ownership."""

        source = self.sources.get(adapter.source_id)
        declared = {endpoint.id for endpoint in source.endpoints}
        executable = set(adapter.endpoint_ids)
        discoverable = set(getattr(adapter, "discovery_endpoint_ids", set()))
        unknown = (executable | discoverable) - declared
        if unknown:
            raise ValueError(
                f"adapter {adapter.name} references unknown endpoints for "
                f"{adapter.source_id}: {sorted(unknown)}"
            )
        if executable.intersection(discoverable):
            raise ValueError(
                f"adapter {adapter.name} marks endpoints as both executable and "
                "discovery-only"
            )
        adapters = self._adapters[adapter.source_id]
        if any(existing.name == adapter.name for existing in adapters):
            raise ValueError(
                f"duplicate adapter {adapter.name} for {adapter.source_id}"
            )
        adapters.append(adapter)

    def get(self, source_id: str) -> list[CatalogSourceAdapter]:
        """Return all registered implementations for a source family."""

        return list(self._adapters.get(source_id, []))

    def for_sources(self, source_ids: Iterable[str]) -> list[CatalogSourceAdapter]:
        """Return adapters in caller routing order, without duplicate instances."""

        selected: list[CatalogSourceAdapter] = []
        seen: set[tuple[str, str]] = set()
        for source_id in source_ids:
            for adapter in self.get(source_id):
                key = (adapter.source_id, adapter.name)
                if key not in seen:
                    selected.append(adapter)
                    seen.add(key)
        return selected

    def all(self) -> list[CatalogSourceAdapter]:
        """Return every adapter in catalog source order."""

        return self.for_sources(source.id for source in self.sources.all())

    def coverage(self) -> RuntimeCoverageRegistry:
        """Build a coverage audit from registered code, not a manual list."""

        coverage = RuntimeCoverageRegistry()
        for adapter in self.all():
            coverage.register(
                adapter.source_id,
                adapter.endpoint_ids,
                discovery_endpoint_ids=getattr(
                    adapter, "discovery_endpoint_ids", set()
                ),
            )
        return coverage
