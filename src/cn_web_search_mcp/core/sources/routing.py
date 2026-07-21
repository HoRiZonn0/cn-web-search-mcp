"""Plan intent-specific sources without replacing mandatory four-source discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .registry import SourceRegistry


class IntentPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    keywords: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    preferred_source_ids: list[str] = Field(default_factory=list)
    verification_source_ids: list[str] = Field(default_factory=list)
    max_sources: int = Field(default=3, ge=1, le=12)


class RoutingCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    intents: list[IntentPolicy] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_intent_ids(self) -> "RoutingCatalog":
        ids = [item.id for item in self.intents]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate intent id in routing catalog")
        if "general" not in ids:
            raise ValueError("routing catalog requires a general intent")
        return self


@dataclass(slots=True)
class PlannedSourceRoute:
    source_id: str
    role: Literal["primary", "fallback", "verification"]
    intents: list[str] = field(default_factory=list)
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SourceRoutingPlan:
    question: str
    intents: list[str]
    routes: list[PlannedSourceRoute]
    evaluated_sources: int
    catalog_scan_completed: bool
    discovery_policy: str = "mandatory-four-source-set-remains-independent"


class SourceRouter:
    """Evaluate the whole catalog, then select bounded vertical-source hints."""

    def __init__(self, registry: SourceRegistry, routing: RoutingCatalog):
        self.registry = registry
        self.routing = routing
        known = {source.id for source in registry.all(enabled_only=False)}
        for policy in routing.intents:
            referenced = set(policy.preferred_source_ids + policy.verification_source_ids)
            missing = sorted(referenced - known)
            if missing:
                raise ValueError(f"intent {policy.id} references unknown sources: {missing}")

    @classmethod
    def load_default(cls, registry: SourceRegistry | None = None) -> "SourceRouter":
        registry = registry or SourceRegistry.load_default()
        resource = files("cn_web_search_mcp").joinpath("data/routing.yaml")
        payload = yaml.safe_load(resource.read_text(encoding="utf-8"))
        return cls(registry, RoutingCatalog.model_validate(payload))

    @classmethod
    def load(cls, path: str | Path, registry: SourceRegistry) -> "SourceRouter":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls(registry, RoutingCatalog.model_validate(payload))

    def plan(self, question: str) -> SourceRoutingPlan:
        normalized = question.casefold()
        policies = [
            policy
            for policy in self.routing.intents
            if policy.id != "general"
            and any(keyword.casefold() in normalized for keyword in policy.keywords)
        ]
        if not policies:
            policies = [next(item for item in self.routing.intents if item.id == "general")]

        sources = self.registry.all()
        merged: dict[str, PlannedSourceRoute] = {}
        for policy in policies:
            ranked: list[tuple[float, str, list[str]]] = []
            for source in sources:  # Always traverse the complete loaded catalog.
                matched_keywords = [
                    keyword
                    for keyword in source.keywords
                    if keyword and keyword.casefold() in normalized
                ]
                entity_hit = source.name.casefold() in normalized
                category_hit = any(
                    category.casefold() in {value.casefold() for value in source.categories}
                    for category in policy.categories
                )
                preferred_index = (
                    policy.preferred_source_ids.index(source.id)
                    if source.id in policy.preferred_source_ids
                    else None
                )
                verification = source.id in policy.verification_source_ids
                if not (matched_keywords or entity_hit or preferred_index is not None or verification):
                    continue
                score = source.authority
                reasons: list[str] = []
                if matched_keywords:
                    score += 100 + len(matched_keywords) * 10
                    reasons.append(f"keyword match: {', '.join(matched_keywords)}")
                if entity_hit:
                    score += 120
                    reasons.append("source name explicitly mentioned")
                if preferred_index is not None:
                    score += 50 - preferred_index
                    reasons.append(f"preferred for {policy.id}")
                if category_hit:
                    score += 5
                if verification:
                    score += 20
                    reasons.append(f"verification source for {policy.id}")
                ranked.append((score, source.id, reasons))

            ranked.sort(key=lambda item: (-item[0], item[1]))
            selected = ranked[: policy.max_sources]
            primary_assigned = False
            for score, source_id, reasons in selected:
                verification = source_id in policy.verification_source_ids
                role: Literal["primary", "fallback", "verification"]
                if verification:
                    role = "verification"
                elif not primary_assigned:
                    role = "primary"
                    primary_assigned = True
                else:
                    role = "fallback"
                existing = merged.get(source_id)
                if existing:
                    if policy.id not in existing.intents:
                        existing.intents.append(policy.id)
                    existing.score = max(existing.score, score)
                    existing.reasons.extend(reason for reason in reasons if reason not in existing.reasons)
                    if existing.role == "fallback" and role in {"primary", "verification"}:
                        existing.role = role
                else:
                    merged[source_id] = PlannedSourceRoute(
                        source_id=source_id,
                        role=role,
                        intents=[policy.id],
                        score=score,
                        reasons=reasons,
                    )

        role_order = {"primary": 0, "verification": 1, "fallback": 2}
        routes = sorted(
            merged.values(),
            key=lambda item: (role_order[item.role], -item.score, item.source_id),
        )
        report = self.registry.full_scan_report()
        return SourceRoutingPlan(
            question=question,
            intents=[policy.id for policy in policies],
            routes=routes,
            evaluated_sources=len(sources),
            catalog_scan_completed=bool(report["validation_completed"]),
        )
