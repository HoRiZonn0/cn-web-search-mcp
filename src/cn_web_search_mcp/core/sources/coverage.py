"""Audit declared catalog endpoints against registered runtime adapters."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .registry import SourceRegistry


class RuntimeCoverageRegistry:
    """Track executable endpoint IDs without conflating metadata and code."""

    def __init__(self) -> None:
        self._endpoints: dict[str, set[str]] = defaultdict(set)

    def register(self, source_id: str, endpoint_ids: Iterable[str]) -> None:
        values = set(endpoint_ids)
        duplicate = self._endpoints[source_id].intersection(values)
        if duplicate:
            raise ValueError(f"duplicate runtime endpoints for {source_id}: {sorted(duplicate)}")
        self._endpoints[source_id].update(values)

    def report(self, registry: SourceRegistry) -> dict:
        sources: dict[str, dict[str, list[str]]] = {}
        executable_total = 0
        declared_total = 0
        for source in registry.all(enabled_only=False):
            declared = {endpoint.id for endpoint in source.endpoints}
            executable = declared.intersection(self._endpoints.get(source.id, set()))
            declared_total += len(declared)
            executable_total += len(executable)
            sources[source.id] = {
                "declared": sorted(declared),
                "executable": sorted(executable),
                "not_implemented": sorted(declared - executable),
            }
        return {
            "declared_endpoint_count": declared_total,
            "executable_endpoint_count": executable_total,
            "sources": sources,
        }
