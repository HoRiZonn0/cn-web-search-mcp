"""Validated source catalog and routing metadata."""

from .models import CatalogProvenance, EndpointDefinition, RatePolicy, SourceCatalog, SourceDefinition
from .registry import DuplicateYamlKeyError, SourceRegistry
from .coverage import RuntimeCoverageRegistry
from .routing import PlannedSourceRoute, SourceRouter, SourceRoutingPlan
from .adapters import CatalogSourceAdapter, SourceAdapterRegistry, build_source_adapter_registry

__all__ = [
    "CatalogProvenance",
    "CatalogSourceAdapter",
    "DuplicateYamlKeyError",
    "EndpointDefinition",
    "RatePolicy",
    "RuntimeCoverageRegistry",
    "SourceCatalog",
    "SourceAdapterRegistry",
    "SourceDefinition",
    "SourceRegistry",
    "SourceRouter",
    "SourceRoutingPlan",
    "PlannedSourceRoute",
    "build_source_adapter_registry",
]
