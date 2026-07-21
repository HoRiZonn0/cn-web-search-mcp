"""Load the whole YAML catalog, reject ambiguity, and expose indexed lookups."""

from __future__ import annotations

import hashlib
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from .models import SourceCatalog, SourceDefinition


class DuplicateYamlKeyError(ValueError):
    """Raised before validation when YAML silently would overwrite a key."""


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader: _UniqueKeyLoader, node, deep: bool = False):
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DuplicateYamlKeyError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


class SourceRegistry:
    """Validated, fully loaded source catalog."""

    def __init__(self, catalog: SourceCatalog, *, catalog_sha256: str):
        self.catalog = catalog
        self.catalog_sha256 = catalog_sha256
        self._sources = {source.id: source for source in catalog.sources}
        self._validate_uniqueness()
        self._validate_fallbacks()

    @classmethod
    def load_default(cls) -> "SourceRegistry":
        resource = files("cn_web_search_mcp").joinpath("data/sources.yaml")
        text = resource.read_text(encoding="utf-8")
        return cls._from_text(text)

    @classmethod
    def load(cls, path: str | Path) -> "SourceRegistry":
        text = Path(path).read_text(encoding="utf-8")
        return cls._from_text(text)

    @classmethod
    def _from_text(cls, text: str) -> "SourceRegistry":
        data = yaml.load(text, Loader=_UniqueKeyLoader)
        if not isinstance(data, dict):
            raise ValueError("source catalog must be a YAML mapping")
        catalog = SourceCatalog.model_validate(data)
        return cls(catalog, catalog_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())

    def _validate_uniqueness(self) -> None:
        if len(self._sources) != len(self.catalog.sources):
            raise ValueError("duplicate source id in catalog")
        endpoint_owners: dict[str, str] = {}
        for source in self.catalog.sources:
            local_ids: set[str] = set()
            for endpoint in source.endpoints:
                if endpoint.id in local_ids:
                    raise ValueError(f"duplicate endpoint {endpoint.id} in {source.id}")
                local_ids.add(endpoint.id)
                owner = endpoint_owners.setdefault(endpoint.id, source.id)
                if owner != source.id:
                    raise ValueError(
                        f"duplicate endpoint id {endpoint.id} in {owner} and {source.id}"
                    )

    def _validate_fallbacks(self) -> None:
        for source in self.catalog.sources:
            for fallback_id in source.fallback_source_ids:
                if fallback_id == source.id:
                    raise ValueError(f"source {source.id} cannot fall back to itself")
                if fallback_id not in self._sources:
                    raise ValueError(f"unknown fallback {fallback_id} for {source.id}")

    def all(self, *, enabled_only: bool = True) -> list[SourceDefinition]:
        sources = self.catalog.sources
        if enabled_only:
            sources = [source for source in sources if source.enabled]
        return list(sources)

    def get(self, source_id: str) -> SourceDefinition:
        try:
            return self._sources[source_id]
        except KeyError as exc:
            raise KeyError(f"unknown source: {source_id}") from exc

    def for_category(self, category: str) -> list[SourceDefinition]:
        normalized = category.casefold()
        return [
            source
            for source in self.all()
            if any(normalized == value.casefold() for value in source.categories)
        ]

    def full_scan_report(self) -> dict[str, Any]:
        loaded = len(self.catalog.sources)
        return {
            "catalog_version": self.catalog.version,
            "declared_sources": self.catalog.declared_sources,
            "loaded_sources": loaded,
            "validation_completed": loaded == self.catalog.declared_sources,
            "catalog_sha256": self.catalog_sha256,
            "source_markdown_sha256": self.catalog.provenance.source_sha256,
        }
