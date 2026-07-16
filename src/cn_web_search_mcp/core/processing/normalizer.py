"""Normalize heterogeneous engine results before scoring."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..models import SearchResult


_TRACKING_KEYS = {
    "from",
    "ref",
    "source",
    "spm",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").casefold()
    if parts.port and not ((parts.scheme == "http" and parts.port == 80) or (parts.scheme == "https" and parts.port == 443)):
        host = f"{host}:{parts.port}"
    query = urlencode(
        sorted((key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key.casefold() not in _TRACKING_KEYS)
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(((parts.scheme or "https").casefold(), host, path, query, ""))


def normalize_result(result: SearchResult) -> SearchResult:
    return replace(
        result,
        title=" ".join(result.title.split()),
        snippet=" ".join(result.snippet.split()),
        canonical_url=canonicalize_url(result.canonical_url or result.url),
        discovered_by=list(dict.fromkeys(result.discovered_by or [result.engine])),
    )
