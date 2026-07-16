"""Compose task planning and evidence evaluation into a stable local Core API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .analyzers import analyze_task
from .engines import REQUIRED_SOURCES
from .knowledge import load_authority_entries, scan_authorities
from .models import Evidence, EvidencePack, Query, SearchResult, SearchTask, StageRecord, StageStatus, TaskType, to_dict
from .planners import plan_queries, plan_retry_queries
from .processing import deduplicate_results, filter_after_cutoff, process_content
from .quality import decide_next_action, normalize_declared_conflicts, score_result, score_round


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = ROOT / "data" / "authoritative-sites.md"


def plan(question: str, requirements: list[str] | None = None) -> dict[str, Any]:
    task = analyze_task(question, requirements)
    entries = load_authority_entries(AUTHORITY_PATH)
    matches = scan_authorities(question, entries)
    return {
        "task": to_dict(task),
        "queries": [to_dict(item) for item in plan_queries(task)],
        "authority_scan": {
            "scanned_entries": len(entries),
            "completed": True,
            "matches": [
                {
                    "entity": item.entry.entity,
                    "category": item.entry.category,
                    "score": item.score,
                    "matched_keywords": item.matched_keywords,
                    "urls": item.entry.urls,
                }
                for item in matches
            ],
        },
        "required_sources": list(REQUIRED_SOURCES),
        "execution_mode": "parallel",
        "completion_policy": "all_attempted",
    }


def _task_from_dict(data: dict[str, Any]) -> SearchTask:
    from .models import Requirement

    return SearchTask(
        task_id=data["task_id"],
        question=data["question"],
        task_type=TaskType(data.get("task_type", "stable")),
        language=data.get("language", "zh-CN"),
        entities=data.get("entities", []),
        requirements=[Requirement(**item) for item in data.get("requirements", [])],
        time_requirement=data.get("time_requirement", {}),
        max_rounds=data.get("max_rounds", 3),
    )


def evaluate(payload: dict[str, Any]) -> EvidencePack:
    task = _task_from_dict(payload["task"])
    results = [SearchResult(**item) for item in payload.get("results", [])]
    stages = [
        StageRecord(**{**item, "status": StageStatus(item["status"])})
        for item in payload.get("stages", [])
    ]
    eligible_results, temporal_rejections = filter_after_cutoff(task, results)
    for result in eligible_results:
        score_result(result, task)
    unique = deduplicate_results(eligible_results)
    processed_documents = {
        result.result_id: process_content(result, task)
        for result in unique
        if result.content
    }

    def evidence_excerpt(result: SearchResult, limit: int) -> str:
        document = processed_documents[result.result_id]
        if document.chunks:
            best = max(document.chunks, key=lambda item: (item.score, -item.start_char))
            positions = [best.text.casefold().find(term) for term in best.matched_terms]
            positions = [position for position in positions if position >= 0]
            if positions:
                start = max(0, min(positions) - limit // 3)
                return best.text[start:start + limit]
            return best.text[:limit]
        return document.text[:limit]

    evidence = [
        Evidence(
            requirement_id=requirement_id,
            claim=result.snippet or evidence_excerpt(result, 240),
            result_id=result.result_id,
            url=result.canonical_url or result.url,
            publisher=result.publisher,
            source_role=result.source_role,
            published_at=result.published_at,
            observed_at=result.observed_at,
            forecast_valid_at=result.forecast_valid_at,
            evidence_text=evidence_excerpt(result, 500) or result.snippet[:500],
            confidence=min(1.0, result.scores.get("total", 0) / 100),
        )
        for result in unique
        for requirement_id in result.matched_requirement_ids
        if result.content
    ]
    conflicts = normalize_declared_conflicts(payload.get("conflicts", []))
    query_ids = {item.query_id for item in stages}
    observed_source_records = [(item.engine, item.query_id) for item in stages]
    required_source_records = {
        (source, query_id)
        for query_id in query_ids
        for source in REQUIRED_SOURCES
    }
    source_set_completed = (
        bool(query_ids)
        and len(observed_source_records) == len(required_source_records)
        and set(observed_source_records) == required_source_records
        and all(item.status is not StageStatus.SKIPPED for item in stages)
    )
    round_number = int(payload.get("round_number", 1))
    quality = score_round(
        task,
        unique,
        evidence,
        round_number=round_number,
        source_set_completed=source_set_completed,
        conflicts=conflicts,
    )
    decision = decide_next_action(task, quality)
    retry_queries = plan_retry_queries(task, quality) if decision.action.value not in {"stop_sufficient", "stop_unresolvable"} else []
    decision.next_queries = [item.text for item in retry_queries]
    status = "sufficient" if decision.action.value == "stop_sufficient" else (
        "unresolvable" if decision.action.value == "stop_unresolvable" else "needs_search"
    )
    trace = {
        "round": round_number,
        "raw_result_count": len(results),
        "temporally_eligible_result_count": len(eligible_results),
        "temporal_rejection_count": len(temporal_rejections),
        "temporal_rejections": [
            {
                "result_id": item.result_id,
                "url": item.url,
                "reason": item.exclusion_reason,
                "published_at": item.published_at,
                "observed_at": item.observed_at,
            }
            for item in temporal_rejections
        ],
        "unique_result_count": len(unique),
        "content_processing": [
            {
                "result_id": item.result_id,
                "mode": item.mode,
                "original_chars": item.original_chars,
                "cleaned_chars": item.cleaned_chars,
                "output_chars": item.output_chars,
                "selected_chunk_ids": [chunk.chunk_id for chunk in item.chunks],
            }
            for item in processed_documents.values()
        ],
        "stage_count": len(stages),
        "source_set_completed": source_set_completed,
    }
    return EvidencePack(
        task=task,
        status=status,
        quality=quality,
        decision=decision,
        evidence=evidence,
        unresolved=quality.missing_requirement_ids,
        conflicts=conflicts,
        trace=trace,
    )
