"""Enforce as-of boundaries before results can become evidence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import SearchResult, SearchTask


def _parse_datetime(value: str, default_tz) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed


def filter_after_cutoff(
    task: SearchTask, results: list[SearchResult]
) -> tuple[list[SearchResult], list[SearchResult]]:
    """Reject post-cutoff publications/observations; keep future forecast validity."""

    cutoff_text = task.time_requirement.get("cutoff")
    if not cutoff_text:
        return results, []
    cutoff = _parse_datetime(cutoff_text, timezone(timedelta(hours=8)))
    eligible: list[SearchResult] = []
    rejected: list[SearchResult] = []
    for result in results:
        reason = None
        for field_name in ("published_at", "observed_at"):
            value = getattr(result, field_name)
            if not value:
                continue
            try:
                timestamp = _parse_datetime(value, cutoff.tzinfo)
            except ValueError:
                reason = f"invalid_{field_name}"
                break
            if timestamp > cutoff:
                reason = f"{field_name}_after_cutoff"
                break
        if reason:
            result.exclusion_reason = reason
            rejected.append(result)
        else:
            eligible.append(result)
    return eligible, rejected
