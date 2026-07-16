"""Merge URL duplicates and near-identical result titles."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..models import SearchResult
from .normalizer import normalize_result


def _title_key(title: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", title.casefold())


def _merge(target: SearchResult, incoming: SearchResult) -> None:
    target.discovered_by = list(dict.fromkeys(target.discovered_by + incoming.discovered_by))
    target.matched_requirement_ids = list(
        dict.fromkeys(target.matched_requirement_ids + incoming.matched_requirement_ids)
    )
    if len(incoming.snippet) > len(target.snippet):
        target.snippet = incoming.snippet
    if incoming.content and (not target.content or len(incoming.content) > len(target.content)):
        target.content = incoming.content
        target.content_status = incoming.content_status
    if incoming.published_at and (not target.published_at or incoming.published_at > target.published_at):
        target.published_at = incoming.published_at


def deduplicate_results(results: list[SearchResult], title_threshold: float = 0.92) -> list[SearchResult]:
    unique: list[SearchResult] = []
    by_url: dict[str, SearchResult] = {}
    for raw in results:
        result = normalize_result(raw)
        if result.canonical_url in by_url:
            _merge(by_url[result.canonical_url], result)
            continue

        title_key = _title_key(result.title)
        duplicate = next(
            (
                candidate
                for candidate in unique
                if title_key
                and SequenceMatcher(None, title_key, _title_key(candidate.title)).ratio() >= title_threshold
                and result.publisher.casefold() == candidate.publisher.casefold()
            ),
            None,
        )
        if duplicate:
            _merge(duplicate, result)
            by_url[result.canonical_url] = duplicate
            continue
        unique.append(result)
        by_url[result.canonical_url] = result
    return unique
