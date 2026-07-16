"""Evaluate whether the result set satisfies the task, not merely result count."""

from __future__ import annotations

from ..models import Evidence, RoundQuality, SearchResult, SearchTask, TaskType


def score_round(
    task: SearchTask,
    results: list[SearchResult],
    evidence: list[Evidence],
    *,
    round_number: int,
    source_set_completed: bool,
    conflicts: list[dict] | None = None,
) -> RoundQuality:
    conflicts = conflicts or []
    required = [item for item in task.requirements if item.priority == "required"]
    supported_ids = {item.requirement_id for item in evidence if item.confidence >= 0.65 and item.evidence_text}
    missing = [item.id for item in required if item.id not in supported_ids]
    coverage = (len(required) - len(missing)) / len(required) if required else 1.0

    strong = [result for result in results if result.scores.get("total", 0) >= 80]
    direct_ids = {item.requirement_id for item in evidence if item.confidence >= 0.8 and item.evidence_text}
    has_direct = bool(direct_ids) if required else bool(strong)
    core_quality = min(1.0, (len(strong) + len(direct_ids)) / max(1, len(required)))

    time_sensitive = task.task_type in {TaskType.REALTIME, TaskType.RECENT, TaskType.VERSIONED}
    dated_evidence = sum(1 for item in evidence if item.published_at or item.observed_at)
    freshness_satisfied = not time_sensitive or (bool(evidence) and dated_evidence == len(evidence))
    freshness = 1.0 if freshness_satisfied else (dated_evidence / len(evidence) if evidence else 0.0)

    publishers = {item.publisher.casefold() for item in evidence if item.publisher}
    independence = min(1.0, len(publishers) / 2) if evidence else 0.0
    critical_conflict = any(item.get("severity") == "critical" and not item.get("resolved") for item in conflicts)
    consistency = 0.0 if critical_conflict else (0.6 if conflicts else 1.0)
    answerability = min(1.0, coverage * 0.8 + (0.2 if has_direct else 0.0))

    total = round(
        coverage * 35
        + core_quality * 20
        + freshness * 15
        + independence * 10
        + consistency * 10
        + answerability * 10,
        2,
    )
    problems: list[dict] = []
    if missing:
        problems.append({"type": "coverage_gap", "targets": missing})
    if not freshness_satisfied:
        problems.append({"type": "freshness_gap"})
    if critical_conflict:
        problems.append({"type": "critical_conflict"})
    if not source_set_completed:
        problems.append({"type": "incomplete_source_set"})

    return RoundQuality(
        round_number=round_number,
        total_score=total,
        coverage=round(coverage, 4),
        core_evidence_quality=round(core_quality, 4),
        freshness=round(freshness, 4),
        source_independence=round(independence, 4),
        consistency=round(consistency, 4),
        answerability=round(answerability, 4),
        source_set_completed=source_set_completed,
        has_direct_core_evidence=has_direct,
        freshness_satisfied=freshness_satisfied,
        unresolved_critical_conflict=critical_conflict,
        missing_requirement_ids=missing,
        problems=problems,
    )
