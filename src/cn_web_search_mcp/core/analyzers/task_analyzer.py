"""Small deterministic baseline; a host model may replace or enrich this output."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ..models import Requirement, SearchTask, TaskType


def _task_type(question: str) -> TaskType:
    if re.search(r"现在|当前|实时|刚刚|台风|天气|比分|股价", question):
        return TaskType.REALTIME
    if re.search(r"最近|近期|最新|本周|今天|昨日", question):
        return TaskType.RECENT
    if re.search(r"版本|价格|定价|发布|更新|弃用|API", question, re.IGNORECASE):
        return TaskType.VERSIONED
    return TaskType.STABLE


def _time_requirement(question: str) -> dict[str, str]:
    """Extract an explicit as-of boundary and normalize it to ISO 8601."""

    patterns = (
        r"截至(?:北京时间)?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(\d{1,2})(?::|时)\s*(\d{1,2})?",
        r"截至(?:北京时间)?\s*(\d{4})-(\d{1,2})-(\d{1,2})[ T](\d{1,2}):(\d{1,2})",
    )
    for pattern in patterns:
        match = re.search(pattern, question)
        if not match:
            continue
        year, month, day, hour, minute = match.groups()
        china_tz = timezone(timedelta(hours=8))
        cutoff = datetime(
            int(year), int(month), int(day), int(hour), int(minute or 0), tzinfo=china_tz
        )
        return {
            "type": "as_of",
            "cutoff": cutoff.isoformat(),
            "timezone": "Asia/Shanghai",
        }
    return {}


def analyze_task(question: str, requirements: list[str] | None = None) -> SearchTask:
    descriptions = requirements or [question.strip()]
    return SearchTask(
        task_id=f"search-{uuid4().hex[:12]}",
        question=question.strip(),
        task_type=_task_type(question),
        requirements=[Requirement(id=f"r{index}", description=text) for index, text in enumerate(descriptions, 1)],
        time_requirement=_time_requirement(question),
    )
