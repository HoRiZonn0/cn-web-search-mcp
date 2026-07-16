"""Map quality defects to a finite next action."""

from __future__ import annotations

from ..models import Decision, DecisionAction, RoundQuality, SearchTask


def decide_next_action(task: SearchTask, quality: RoundQuality) -> Decision:
    can_stop = (
        quality.source_set_completed
        and quality.coverage >= 0.8
        and quality.has_direct_core_evidence
        and quality.freshness_satisfied
        and not quality.unresolved_critical_conflict
        and quality.total_score >= 85
    )
    if can_stop:
        return Decision(DecisionAction.STOP_SUFFICIENT, "硬性条件和综合评分均已满足")
    if quality.round_number >= task.max_rounds:
        return Decision(
            DecisionAction.STOP_UNRESOLVABLE,
            "已达到最大搜索轮次，仍有未满足的硬性条件",
            quality.missing_requirement_ids,
        )
    if not quality.source_set_completed:
        return Decision(DecisionAction.REFINE_QUERIES, "四个必需来源记录不完整，必须重新执行四源完整搜索")
    if quality.unresolved_critical_conflict:
        return Decision(DecisionAction.VERIFY_CONFLICT, "关键来源存在尚未解决的冲突")
    if not quality.freshness_satisfied:
        return Decision(
            DecisionAction.SEARCH_FRESHER_SOURCE,
            "时间敏感任务缺少带明确数据时间的证据",
            quality.missing_requirement_ids,
        )
    if quality.missing_requirement_ids:
        return Decision(
            DecisionAction.SEARCH_MISSING_REQUIREMENT,
            "必需信息项覆盖不足",
            quality.missing_requirement_ids,
        )
    if not quality.has_direct_core_evidence:
        return Decision(DecisionAction.FETCH_PRIMARY_CONTENT, "当前只有摘要或间接材料，需要获取原始正文")
    return Decision(DecisionAction.REFINE_QUERIES, "综合质量未达到停止阈值")
