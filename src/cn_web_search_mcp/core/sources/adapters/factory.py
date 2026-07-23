"""Construct the default source-adapter registry from packaged metadata."""

from __future__ import annotations

from ....config import Settings
from ....network import HttpClient
from ....search_adapters import build_search_adapters
from ....structured_adapters import build_structured_adapters
from ..registry import SourceRegistry
from .catalog import build_catalog_discovery_adapters
from .registry import SourceAdapterRegistry


def build_source_adapter_registry(
    settings: Settings,
    client: HttpClient | None = None,
    sources: SourceRegistry | None = None,
) -> SourceAdapterRegistry:
    """Register mandatory, direct structured, and catalog discovery adapters."""

    client = client or HttpClient(settings)
    sources = sources or SourceRegistry.load_default()
    registry = SourceAdapterRegistry(sources)

    search_adapters = build_search_adapters(settings, client)
    for adapter in search_adapters:
        registry.register(adapter)

    direct_source_ids = {
        source.id
        for source in sources.all()
        if any(endpoint.adapter for endpoint in source.endpoints)
    }
    for adapter in build_structured_adapters(direct_source_ids, settings, client):
        registry.register(adapter)

    web_backend = next(adapter for adapter in search_adapters if adapter.name == "web_search")
    for adapter in build_catalog_discovery_adapters(sources, web_backend):
        registry.register(adapter)
    return registry
