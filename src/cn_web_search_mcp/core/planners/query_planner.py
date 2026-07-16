"""Produce baseline query groups while allowing host-model enrichment."""

from __future__ import annotations

import re

from ..models import Query, SearchTask, TaskType


def _compact(text: str) -> str:
    text = re.sub(r"[，。！？,.!?;；：:]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def plan_queries(task: SearchTask) -> list[Query]:
    base = _compact(task.question)
    queries = [Query(id="q1", text=base, requirement_ids=[item.id for item in task.requirements])]
    complex_task = len(task.requirements) > 1 or bool(re.search(r"对比|以及|分别|和|与|哪些|情况", base))
    if complex_task:
        for index, requirement in enumerate(task.requirements, 2):
            queries.append(Query(id=f"q{index}", text=_compact(requirement.description), requirement_ids=[requirement.id]))
    elif task.task_type in {TaskType.REALTIME, TaskType.RECENT, TaskType.VERSIONED}:
        queries.append(Query(id="q2", text=f"{base} 官方 最新", requirement_ids=[item.id for item in task.requirements]))
    return queries
