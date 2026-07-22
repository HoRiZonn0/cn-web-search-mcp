"""Domain-restricted discovery adapters generated from catalog metadata."""

from __future__ import annotations

import hashlib
from urllib.parse import urlsplit

from ...engines import EngineAdapter, EngineResponse
from ...models import Query, StageStatus
from ..models import SourceDefinition


def _host_matches(host: str, domains: set[str]) -> bool:
    normalized = host.casefold().removeprefix("www.").rstrip(".")
    return any(normalized == domain or normalized.endswith(f".{domain}") for domain in domains)


def _source_role(value: str) -> str:
    return {
        "official_primary": "primary_official",
        "official_media": "official_media",
        "secondary_media": "secondary",
        "curated_reference": "curated_reference",
    }.get(value, "unknown")


class CatalogDiscoveryAdapter:
    """Search one catalogued source through a shared web-search backend.

    This adapter makes every selected catalog source actionable without
    pretending that a homepage is a first-party API. Its endpoints therefore
    remain explicitly discovery-only in runtime coverage.
    """

    endpoint_ids: set[str] = set()

    def __init__(self, source: SourceDefinition, backend: EngineAdapter) -> None:
        self.source = source
        self.source_id = source.id
        self.name = f"catalog_{source.id}"
        self.backend = backend
        self.domains = {
            domain.casefold().removeprefix("www.").rstrip("/")
            for domain in source.domains
            if domain.strip()
        }
        self.discovery_endpoint_ids = {
            endpoint.id
            for endpoint in source.endpoints
            if endpoint.discovery_only
            and endpoint.method in {"homepage", "site_search", "web_search"}
        }

    def search(self, query: Query) -> EngineResponse:
        if not self.domains or not self.discovery_endpoint_ids:
            return EngineResponse(StageStatus.SKIPPED, error="no searchable catalog domains")
        site_filter = " OR ".join(f"site:{domain}" for domain in sorted(self.domains))
        scoped = Query(
            id=query.id,
            text=f"({site_filter}) {query.text}",
            requirement_ids=list(query.requirement_ids),
            round_number=query.round_number,
        )
        response = self.backend.search(scoped)
        if response.status not in {StageStatus.SUCCESS, StageStatus.EMPTY}:
            return response

        selected = []
        for result in response.results:
            host = urlsplit(result.url).hostname or ""
            if not _host_matches(host, self.domains):
                continue
            digest = hashlib.sha256(
                f"{self.name}\0{query.id}\0{result.url}".encode()
            ).hexdigest()[:20]
            original_discovery = list(result.discovered_by)
            result.result_id = f"{self.name}-{digest}"
            result.engine = self.name
            result.query_id = query.id
            result.publisher = host
            result.source_role = _source_role(self.source.source_role)
            result.discovered_by = [
                self.name,
                *(item for item in original_discovery if item != self.name),
            ]
            result.search_channel = "catalog_source"
            selected.append(result)
        return EngineResponse(
            StageStatus.SUCCESS if selected else StageStatus.EMPTY,
            selected,
        )


def build_catalog_discovery_adapters(
    sources,
    backend: EngineAdapter,
) -> list[CatalogDiscoveryAdapter]:
    """Build one bounded, domain-aware adapter for each searchable catalog source."""

    adapters: list[CatalogDiscoveryAdapter] = []
    for source in sources.all():
        if source.source_role == "search_channel":
            continue
        adapter = CatalogDiscoveryAdapter(source, backend)
        if adapter.discovery_endpoint_ids and adapter.domains:
            adapters.append(adapter)
    return adapters
