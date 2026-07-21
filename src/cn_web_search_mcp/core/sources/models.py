"""Strict models for static source metadata."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Identifier = str


class CatalogProvenance(BaseModel):
    """Describe where and when a catalog was produced."""

    model_config = ConfigDict(extra="forbid")

    source_file: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    migration: str


class RatePolicy(BaseModel):
    """Conservative defaults for one source family."""

    model_config = ConfigDict(extra="forbid")

    serial_only: bool = False
    minimum_interval_seconds: float = Field(default=0, ge=0)
    max_concurrency: int = Field(default=1, ge=1, le=32)
    timeout_seconds: float = Field(default=15, gt=0, le=120)


class EndpointDefinition(BaseModel):
    """One declared endpoint; metadata never makes it executable by itself."""

    model_config = ConfigDict(extra="forbid")

    id: Identifier = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    method: Literal[
        "homepage",
        "site_search",
        "web_search",
        "rss",
        "http_api",
        "structured_api",
    ]
    url: str | None = None
    query_template: str | None = None
    discovery_only: bool = True
    evidence_eligible: bool = False
    requires_key: bool = False
    key_env: str | None = None
    adapter: str | None = None

    @model_validator(mode="after")
    def validate_location_and_key(self) -> "EndpointDefinition":
        if not self.url and not self.query_template:
            raise ValueError("endpoint requires url or query_template")
        if self.requires_key and not self.key_env:
            raise ValueError("key_env is required when requires_key is true")
        if self.discovery_only and self.evidence_eligible:
            raise ValueError("discovery-only endpoints cannot be evidence eligible")
        return self


class SourceDefinition(BaseModel):
    """A source family and its static routing attributes."""

    model_config = ConfigDict(extra="forbid")

    id: Identifier = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1)
    legacy_entity: str = Field(min_length=1)
    legacy_category: str = Field(min_length=1)
    categories: list[str] = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    source_role: Literal[
        "curated_reference",
        "official_primary",
        "official_media",
        "secondary_media",
        "search_channel",
        "unknown",
    ] = "curated_reference"
    authority: int = Field(default=3, ge=1, le=5)
    reliability: Literal["unknown", "low", "medium", "high"] = "unknown"
    languages: list[str] = Field(default_factory=lambda: ["zh-CN"])
    capabilities: list[str] = Field(default_factory=lambda: ["authority_discovery"])
    enabled: bool = True
    fallback_source_ids: list[Identifier] = Field(default_factory=list)
    rate_policy: RatePolicy = Field(default_factory=RatePolicy)
    endpoints: list[EndpointDefinition] = Field(min_length=1)
    provenance: str = Field(min_length=1)


class SourceCatalog(BaseModel):
    """Complete catalog document loaded and validated as one unit."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    declared_sources: int = Field(ge=1)
    provenance: CatalogProvenance
    sources: list[SourceDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_declared_count(self) -> "SourceCatalog":
        if self.declared_sources != len(self.sources):
            raise ValueError(
                f"declared_sources={self.declared_sources} but loaded {len(self.sources)}"
            )
        return self
