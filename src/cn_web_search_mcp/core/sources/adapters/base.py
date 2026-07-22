"""Common runtime contract for catalog-backed source adapters."""

from __future__ import annotations

from typing import Protocol

from ...engines import EngineResponse
from ...models import Query


class CatalogSourceAdapter(Protocol):
    """One executable or discovery-only implementation for a catalog source."""

    name: str
    source_id: str
    endpoint_ids: set[str]

    @property
    def discovery_endpoint_ids(self) -> set[str]:
        """Catalog endpoints used only to discover candidates, not direct evidence."""

        ...

    def search(self, query: Query) -> EngineResponse:
        """Run the adapter and return the shared normalized result shape."""

        ...
