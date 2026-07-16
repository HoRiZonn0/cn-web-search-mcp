"""Score one candidate as evidence, auxiliary material, a lead, or noise."""

from __future__ import annotations

from urllib.parse import urlsplit

from ..models import SearchResult, SearchTask, TaskType


_OFFICIAL_SUFFIXES = (".gov.cn", ".gov", ".edu", ".edu.cn", ".org")


def score_result(result: SearchResult, task: SearchTask) -> float:
    haystack = f"{result.title} {result.snippet} {result.content or ''}".casefold()
    required_terms = [term.casefold() for term in task.entities if term]
    relevance = 25.0 if required_terms and all(term in haystack for term in required_terms) else 12.0
    if result.matched_requirement_ids:
        relevance = min(25.0, relevance + 5.0)

    host = (urlsplit(result.canonical_url or result.url).hostname or "").casefold()
    authority = 20.0 if result.source_role == "primary_official" or host.endswith(_OFFICIAL_SUFFIXES) else 10.0
    freshness = 20.0
    if (
        task.task_type in {TaskType.REALTIME, TaskType.RECENT, TaskType.VERSIONED}
        and not result.published_at
        and not result.observed_at
    ):
        freshness = 5.0

    content_usability = 15.0 if result.content_status == "fetched" and result.content else 6.0
    evidence_directness = 15.0 if result.content and result.matched_requirement_ids else 7.0
    traceability = 5.0 if result.url and (result.publisher or result.published_at) else 3.0
    total = relevance + authority + freshness + content_usability + evidence_directness + traceability

    # A snippet-only result is a lead, never core evidence.
    if not result.content:
        total = min(total, 64.0)
    result.scores.update(
        {
            "relevance": relevance,
            "authority": authority,
            "freshness": freshness,
            "content_usability": content_usability,
            "evidence_directness": evidence_directness,
            "traceability": traceability,
            "total": total,
        }
    )
    return total
