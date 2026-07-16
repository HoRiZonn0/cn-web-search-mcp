"""Score authority entries only after the complete knowledge base was scanned."""

from __future__ import annotations

from dataclasses import dataclass

from .loader import AuthorityEntry


_WEAK_KEYWORDS = {
    "app数据",
    "command",
    "english",
    "model",
    "type",
    "办公",
    "工具",
    "数据",
    "文档",
    "新闻",
    "分析",
    "评测",
    "教程",
    "最新",
}


@dataclass(slots=True)
class AuthorityMatch:
    entry: AuthorityEntry
    score: float
    matched_keywords: list[str]


def scan_authorities(
    question: str,
    entries: list[AuthorityEntry],
    *,
    limit: int = 3,
) -> list[AuthorityMatch]:
    """Evaluate every entry, then rank matches; never return during iteration."""

    normalized = question.casefold()
    matches: list[AuthorityMatch] = []
    for entry in entries:
        matched = [
            keyword
            for keyword in entry.keywords
            if keyword and keyword not in _WEAK_KEYWORDS and keyword in normalized
        ]
        entity_hit = entry.entity.casefold() in normalized
        if matched or entity_hit:
            score = min(1.0, len(matched) * 0.25 + (0.5 if entity_hit else 0.0))
            matches.append(AuthorityMatch(entry=entry, score=score, matched_keywords=matched))

    matches.sort(key=lambda item: (-item.score, item.entry.entity))
    return matches[:limit]
