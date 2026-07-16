"""Shared data contracts used by the local Core and future API adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    REALTIME = "realtime"
    RECENT = "recent"
    VERSIONED = "versioned"
    STABLE = "stable"


class StageStatus(str, Enum):
    SUCCESS = "success"
    EMPTY = "empty"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"


class DecisionAction(str, Enum):
    STOP_SUFFICIENT = "stop_sufficient"
    SEARCH_MISSING_REQUIREMENT = "search_missing_requirement"
    REFINE_QUERIES = "refine_queries"
    TARGET_OFFICIAL_SOURCE = "target_official_source"
    VERIFY_CONFLICT = "verify_conflict"
    SEARCH_FRESHER_SOURCE = "search_fresher_source"
    FETCH_PRIMARY_CONTENT = "fetch_primary_content"
    STOP_UNRESOLVABLE = "stop_unresolvable"


@dataclass(slots=True)
class Requirement:
    id: str
    description: str
    priority: str = "required"


@dataclass(slots=True)
class SearchTask:
    task_id: str
    question: str
    task_type: TaskType = TaskType.STABLE
    language: str = "zh-CN"
    entities: list[str] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    time_requirement: dict[str, Any] = field(default_factory=dict)
    max_rounds: int = 3


@dataclass(slots=True)
class Query:
    id: str
    text: str
    requirement_ids: list[str] = field(default_factory=list)
    round_number: int = 1


@dataclass(slots=True)
class StageRecord:
    engine: str
    status: StageStatus
    query_id: str
    result_count: int = 0
    elapsed_ms: int = 0
    error: str | None = None


@dataclass(slots=True)
class SearchResult:
    result_id: str
    engine: str
    query_id: str
    title: str
    url: str
    snippet: str = ""
    canonical_url: str = ""
    publisher: str = ""
    published_at: str | None = None
    observed_at: str | None = None
    forecast_valid_at: str | None = None
    retrieved_at: str | None = None
    content: str | None = None
    content_status: str = "not_fetched"
    source_role: str = "unknown"
    exclusion_reason: str | None = None
    discovered_by: list[str] = field(default_factory=list)
    matched_requirement_ids: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    search_channel: str = ""
    search_backend: str = ""
    upstream_engine: str = ""
    fetch_engine: str = ""
    fetch_status_code: int | None = None
    cache_state: str = "miss"


@dataclass(slots=True)
class DocumentChunk:
    chunk_id: str
    text: str
    start_char: int
    end_char: int
    score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProcessedDocument:
    result_id: str
    mode: str
    original_chars: int
    cleaned_chars: int
    output_chars: int
    text: str
    chunks: list[DocumentChunk] = field(default_factory=list)


@dataclass(slots=True)
class Evidence:
    requirement_id: str
    claim: str
    result_id: str
    url: str
    publisher: str = ""
    source_role: str = "unknown"
    published_at: str | None = None
    observed_at: str | None = None
    forecast_valid_at: str | None = None
    evidence_text: str = ""
    confidence: float = 0.0


@dataclass(slots=True)
class RoundQuality:
    round_number: int
    total_score: float
    coverage: float
    core_evidence_quality: float
    freshness: float
    source_independence: float
    consistency: float
    answerability: float
    source_set_completed: bool
    has_direct_core_evidence: bool
    freshness_satisfied: bool
    unresolved_critical_conflict: bool
    missing_requirement_ids: list[str] = field(default_factory=list)
    problems: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class Decision:
    action: DecisionAction
    reason: str
    target_requirement_ids: list[str] = field(default_factory=list)
    next_queries: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EvidencePack:
    task: SearchTask
    status: str
    quality: RoundQuality
    decision: Decision
    evidence: list[Evidence] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)


def to_dict(value: Any) -> dict[str, Any]:
    """Convert a Core dataclass tree to JSON-compatible dictionaries."""

    return asdict(value)
