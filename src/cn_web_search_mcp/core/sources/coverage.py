"""Audit declared catalog endpoints against registered runtime adapters."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .registry import SourceRegistry


class RuntimeCoverageRegistry:
    """Track executable endpoint IDs without conflating metadata and code."""

    def __init__(self) -> None:
        self._endpoints: dict[str, set[str]] = defaultdict(set)
        self._discovery_endpoints: dict[str, set[str]] = defaultdict(set)

    def register(
        self,
        source_id: str,
        endpoint_ids: Iterable[str],
        *,
        discovery_endpoint_ids: Iterable[str] = (),
    ) -> None:
        values = set(endpoint_ids)
        discovery_values = set(discovery_endpoint_ids)
        overlap = values.intersection(discovery_values)
        if overlap:
            raise ValueError(
                f"endpoints cannot be executable and discovery-only: {sorted(overlap)}"
            )
        duplicate = self._endpoints[source_id].intersection(values)
        if duplicate:
            raise ValueError(f"duplicate runtime endpoints for {source_id}: {sorted(duplicate)}")
        discovery_duplicate = self._discovery_endpoints[source_id].intersection(
            discovery_values
        )
        if discovery_duplicate:
            raise ValueError(
                f"duplicate discovery endpoints for {source_id}: "
                f"{sorted(discovery_duplicate)}"
            )
        cross_duplicate = self._endpoints[source_id].intersection(discovery_values)
        cross_duplicate.update(self._discovery_endpoints[source_id].intersection(values))
        if cross_duplicate:
            raise ValueError(
                f"endpoint coverage type conflicts for {source_id}: "
                f"{sorted(cross_duplicate)}"
            )
        self._endpoints[source_id].update(values)
        self._discovery_endpoints[source_id].update(discovery_values)

    def report(self, registry: SourceRegistry) -> dict:
        sources: dict[str, dict[str, list[str]]] = {}
        executable_total = 0
        discovery_total = 0
        declared_total = 0
        for source in registry.all(enabled_only=False):
            declared = {endpoint.id for endpoint in source.endpoints}
            executable = declared.intersection(self._endpoints.get(source.id, set()))
            discoverable = declared.intersection(
                self._discovery_endpoints.get(source.id, set())
            )
            declared_total += len(declared)
            executable_total += len(executable)
            discovery_total += len(discoverable)
            sources[source.id] = {
                "declared": sorted(declared),
                "executable": sorted(executable),
                "discovery_only": sorted(discoverable),
                "not_implemented": sorted(declared - executable - discoverable),
            }
        return {
            "declared_endpoint_count": declared_total,
            "executable_endpoint_count": executable_total,
            "discovery_endpoint_count": discovery_total,
            "sources": sources,
        }
