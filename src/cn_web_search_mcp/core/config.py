"""Runtime limits shared by local adapters and host job manifests."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    max_query_concurrency: int = 3
    max_stage_concurrency: int = 8
    stage_timeout_seconds: float = 8.0
    max_fetch_concurrency: int = 6
    fetch_timeout_seconds: float = 15.0
    per_domain_concurrency: int = 1
    per_domain_delay_ms: int = 500
    max_fetches_per_round: int = 20

    def __post_init__(self) -> None:
        integer_fields = (
            "max_query_concurrency",
            "max_stage_concurrency",
            "max_fetch_concurrency",
            "per_domain_concurrency",
            "max_fetches_per_round",
        )
        for name in integer_fields:
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be at least 1")
        if self.stage_timeout_seconds <= 0:
            raise ValueError("stage_timeout_seconds must be positive")
        if self.fetch_timeout_seconds <= 0:
            raise ValueError("fetch_timeout_seconds must be positive")
        if self.per_domain_delay_ms < 0:
            raise ValueError("per_domain_delay_ms cannot be negative")

    @classmethod
    def from_env(cls) -> "ExecutionLimits":
        return cls(
            max_query_concurrency=int(os.getenv("CNWS_MAX_QUERY_CONCURRENCY", "3")),
            max_stage_concurrency=int(os.getenv("CNWS_MAX_STAGE_CONCURRENCY", "8")),
            stage_timeout_seconds=float(os.getenv("CNWS_STAGE_TIMEOUT_SECONDS", "8")),
            max_fetch_concurrency=int(os.getenv("CNWS_MAX_FETCH_CONCURRENCY", "6")),
            fetch_timeout_seconds=float(os.getenv("CNWS_FETCH_TIMEOUT_SECONDS", "15")),
            per_domain_concurrency=int(os.getenv("CNWS_PER_DOMAIN_CONCURRENCY", "1")),
            per_domain_delay_ms=int(os.getenv("CNWS_PER_DOMAIN_DELAY_MS", "500")),
            max_fetches_per_round=int(os.getenv("CNWS_MAX_FETCHES_PER_ROUND", "20")),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ContentProcessingConfig:
    """Deterministic limits for direct-pass and extractive compression."""

    direct_pass_chars: int = 4_000
    semantic_compression_chars: int = 12_000
    chunk_chars: int = 1_200
    chunk_overlap_chars: int = 150
    max_selected_chunks: int = 8

    def __post_init__(self) -> None:
        if self.direct_pass_chars < 1:
            raise ValueError("direct_pass_chars must be positive")
        if self.semantic_compression_chars < self.direct_pass_chars:
            raise ValueError("semantic_compression_chars cannot be smaller than direct_pass_chars")
        if self.chunk_chars < 1:
            raise ValueError("chunk_chars must be positive")
        if not 0 <= self.chunk_overlap_chars < self.chunk_chars:
            raise ValueError("chunk_overlap_chars must be between 0 and chunk_chars")
        if self.max_selected_chunks < 1:
            raise ValueError("max_selected_chunks must be positive")

    @classmethod
    def from_env(cls) -> "ContentProcessingConfig":
        return cls(
            direct_pass_chars=int(os.getenv("CNWS_DIRECT_PASS_CHARS", "4000")),
            semantic_compression_chars=int(os.getenv("CNWS_SEMANTIC_COMPRESSION_CHARS", "12000")),
            chunk_chars=int(os.getenv("CNWS_CHUNK_CHARS", "1200")),
            chunk_overlap_chars=int(os.getenv("CNWS_CHUNK_OVERLAP_CHARS", "150")),
            max_selected_chunks=int(os.getenv("CNWS_MAX_SELECTED_CHUNKS", "8")),
        )

    def to_dict(self) -> dict:
        return asdict(self)
