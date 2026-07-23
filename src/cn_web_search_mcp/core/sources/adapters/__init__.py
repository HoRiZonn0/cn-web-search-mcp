"""Runtime adapters bound to the validated source catalog."""

from .base import CatalogSourceAdapter
from .catalog import CatalogDiscoveryAdapter, build_catalog_discovery_adapters
from .factory import build_source_adapter_registry
from .registry import SourceAdapterRegistry

__all__ = [
    "CatalogDiscoveryAdapter",
    "CatalogSourceAdapter",
    "SourceAdapterRegistry",
    "build_catalog_discovery_adapters",
    "build_source_adapter_registry",
]
