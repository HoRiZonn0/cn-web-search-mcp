"""Generate deterministic fallback queries from a finite decision action."""

from __future__ import annotations

from ..models import DecisionAction, Query, RoundQuality, SearchTask


def plan_retry_queries(task: SearchTask, quality: RoundQuality) -> list[Query]:
    requirements = {item.id: item.description for item in task.requirements}
    targets = quality.missing_requirement_ids or list(requirements)
    suffix = "官方 来源"
    if not quality.freshness_satisfied:
        suffix = "官方 最新 更新时间"
    if quality.unresolved_critical_conflict:
        suffix = "官方 公告 原文"
    round_number = quality.round_number + 1
    return [
        Query(
            id=f"r{round_number}q{index}",
            text=f"{requirements[item_id]} {suffix}",
            requirement_ids=[item_id],
            round_number=round_number,
        )
        for index, item_id in enumerate(targets, 1)
        if item_id in requirements
    ]
