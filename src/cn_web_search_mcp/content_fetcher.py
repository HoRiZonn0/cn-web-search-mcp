"""Concurrent page acquisition and deterministic main-text extraction."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urlsplit

from .config import Settings
from .core.config import ExecutionLimits
from .core.fetching import FetchCoordinator
from .core.models import SearchResult
from .network import HttpClient, decode_body


_BLOCKED_MARKERS = (
    "访问过于频繁",
    "请输入验证码",
    "安全验证",
    "enable javascript and cookies",
    "verify you are human",
    "robot check",
    "cf-chl-",
)
_DATE_RE = re.compile(r"(?<!\d)(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})(?:日)?(?:[ T](\d{1,2}):?(\d{2})?)?")


class CacheProtocol(Protocol):
    def cache_get(self, url: str, max_age_seconds: int) -> dict | None: ...
    def cache_put(self, url: str, payload: dict) -> None: ...
    def domain_health_get(self, domain: str) -> dict | None: ...
    def domain_health_record(self, domain: str, status: str, elapsed_ms: int) -> None: ...


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self.metadata: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs):
        tag = tag.casefold()
        values = {key.casefold(): value for key, value in attrs if value}
        if tag in {"script", "style", "noscript", "svg", "canvas", "template", "nav", "footer"}:
            self.skip_depth += 1
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").casefold()
            value = values.get("content")
            if key and value:
                self.metadata[key] = value
        if tag in {"p", "div", "section", "article", "main", "li", "h1", "h2", "h3", "br", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        tag = tag.casefold()
        if tag in {"script", "style", "noscript", "svg", "canvas", "template", "nav", "footer"} and self.skip_depth:
            self.skip_depth -= 1
        if tag == "title":
            self.in_title = False
        if tag in {"p", "div", "section", "article", "main", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str):
        if self.skip_depth:
            return
        if self.in_title:
            self.title_parts.append(data)
        self.parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)


@dataclass(slots=True)
class FetchedDocument:
    requested_url: str
    final_url: str
    status: str
    status_code: int
    content: str = ""
    title: str = ""
    published_at: str | None = None
    error: str | None = None
    cache_state: str = "miss"
    engine: str = "http"
    elapsed_ms: int = 0


def _publication_date(metadata: dict[str, str], headers: dict[str, str], text: str) -> str | None:
    for key in (
        "article:published_time",
        "date",
        "datepublished",
        "pubdate",
        "publishdate",
        "og:published_time",
        "article:modified_time",
    ):
        value = metadata.get(key)
        if value:
            return value.strip()
    last_modified = headers.get("last-modified")
    if last_modified:
        try:
            return parsedate_to_datetime(last_modified).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
    match = _DATE_RE.search(text[:6000])
    if match:
        year, month, day, hour, minute = match.groups()
        return datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0)).isoformat()
    return None


class ContentFetcher:
    def __init__(self, settings: Settings, client: HttpClient | None = None, cache: CacheProtocol | None = None):
        self.settings = settings
        self.client = client or HttpClient(settings)
        self.cache = cache

    def _http_fetch(self, url: str) -> FetchedDocument:
        timeout = self.settings.fetch_timeout_seconds
        if self.settings.firecrawl_endpoint:
            timeout = min(timeout, self.settings.firecrawl_http_timeout_seconds)
        try:
            response = self.client.get(url, timeout=timeout)
            raw = decode_body(response)
        except Exception as exc:
            return FetchedDocument(url, url, "error", 0, error=str(exc))

        lowered = raw.casefold()
        if response.status_code in {401, 403, 429} or any(marker in lowered for marker in _BLOCKED_MARKERS):
            document = FetchedDocument(url, response.url, "blocked", response.status_code, error="anti-bot or access restriction detected", elapsed_ms=response.elapsed_ms)
        elif not 200 <= response.status_code < 400:
            document = FetchedDocument(url, response.url, "error", response.status_code, error=f"HTTP {response.status_code}", elapsed_ms=response.elapsed_ms)
        else:
            content_type = response.headers.get("content-type", "")
            if "html" in content_type or "<html" in lowered[:1000]:
                parser = _TextExtractor()
                parser.feed(raw)
                content = parser.text()
                title = " ".join("".join(parser.title_parts).split())
                published_at = _publication_date(parser.metadata, response.headers, content)
            elif any(kind in content_type for kind in ("text/", "json", "xml")):
                content = raw.strip()
                title = ""
                published_at = _publication_date({}, response.headers, content)
            else:
                content = ""
                title = ""
                published_at = None
            if len(content) < 80:
                document = FetchedDocument(url, response.url, "empty", response.status_code, content=content, title=title, published_at=published_at, error="page did not contain usable text", elapsed_ms=response.elapsed_ms)
            else:
                document = FetchedDocument(url, response.url, "success", response.status_code, content=content, title=title, published_at=published_at, elapsed_ms=response.elapsed_ms)
        return document

    def _firecrawl_fetch(self, url: str) -> FetchedDocument:
        if not self.settings.firecrawl_endpoint:
            return FetchedDocument(url, url, "error", 0, error="Firecrawl is not configured", engine="firecrawl")
        endpoint = self.settings.firecrawl_endpoint.rstrip("/")
        if not endpoint.endswith("/v2/scrape"):
            endpoint += "/v2/scrape"
        headers = {}
        if self.settings.firecrawl_api_key:
            headers["Authorization"] = f"Bearer {self.settings.firecrawl_api_key}"
        try:
            response = self.client.post_json(
                endpoint,
                {
                    "url": url,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                    "maxAge": self.settings.cache_ttl_seconds * 1000,
                    "timeout": int(self.settings.fetch_timeout_seconds * 1000),
                },
                timeout=self.settings.fetch_timeout_seconds + 2,
                headers=headers,
                trusted_network=True,
            )
            payload = json.loads(decode_body(response)) if response.body else {}
        except Exception as exc:
            return FetchedDocument(url, url, "error", 0, error=str(exc), engine="firecrawl")
        data = payload.get("data") or {}
        metadata = data.get("metadata") or {}
        content = str(data.get("markdown") or data.get("content") or "").strip()
        status_code = int(metadata.get("statusCode") or response.status_code)
        final_url = str(metadata.get("sourceURL") or metadata.get("url") or url)
        if not payload.get("success", response.status_code < 400) or not 200 <= status_code < 400:
            return FetchedDocument(url, final_url, "error", status_code, error=str(payload.get("error") or f"HTTP {status_code}"), engine="firecrawl", elapsed_ms=response.elapsed_ms)
        if len(content) < 80:
            return FetchedDocument(url, final_url, "empty", status_code, content=content, error="Firecrawl returned no usable markdown", engine="firecrawl", elapsed_ms=response.elapsed_ms)
        published_at = metadata.get("publishedTime") or metadata.get("published_at") or metadata.get("modifiedTime")
        return FetchedDocument(
            url,
            final_url,
            "success",
            status_code,
            content=content,
            title=str(metadata.get("title") or ""),
            published_at=str(published_at) if published_at else None,
            engine="firecrawl",
            elapsed_ms=response.elapsed_ms,
        )

    def fetch_one(self, url: str) -> FetchedDocument:
        if self.cache:
            cached = self.cache.cache_get(url, self.settings.cache_ttl_seconds)
            if cached:
                return FetchedDocument(**{**cached, "cache_state": "hit"})

        domain = (urlsplit(url).hostname or "").casefold()
        prefer_firecrawl = False
        if self.cache and self.settings.firecrawl_endpoint:
            health = self.cache.domain_health_get(domain)
            if health and health["attempts"] >= 2:
                prefer_firecrawl = (health["blocked"] + health["errors"]) / health["attempts"] >= 0.5

        primary = self._firecrawl_fetch(url) if prefer_firecrawl else self._http_fetch(url)
        document = primary
        attempts = [primary]
        if primary.status != "success" and self.settings.firecrawl_endpoint:
            fallback = self._http_fetch(url) if prefer_firecrawl else self._firecrawl_fetch(url)
            attempts.append(fallback)
            if fallback.status == "success" or (primary.status == "error" and fallback.status != "error"):
                document = replace(fallback, elapsed_ms=primary.elapsed_ms + fallback.elapsed_ms)
            else:
                document = replace(primary, elapsed_ms=primary.elapsed_ms + fallback.elapsed_ms)

        if self.cache:
            for attempt in attempts:
                self.cache.domain_health_record(domain, attempt.status, attempt.elapsed_ms)

        if self.cache and document.status == "success":
            self.cache.cache_put(url, {
                "requested_url": document.requested_url,
                "final_url": document.final_url,
                "status": document.status,
                "status_code": document.status_code,
                "content": document.content,
                "title": document.title,
                "published_at": document.published_at,
                "error": document.error,
                "engine": document.engine,
                "cache_state": "miss",
                "elapsed_ms": document.elapsed_ms,
            })
        return document

    async def enrich_results(
        self,
        results: list[SearchResult],
        *,
        authority_hosts: set[str] | None = None,
    ) -> list[SearchResult]:
        authority_hosts = authority_hosts or set()
        selected = [
            result
            for result in results
            if not (result.content_status == "fetched" and result.content)
        ][: self.settings.max_fetches_per_round]
        limits = ExecutionLimits(
            max_query_concurrency=3,
            max_stage_concurrency=8,
            stage_timeout_seconds=self.settings.request_timeout_seconds,
            max_fetch_concurrency=min(6, self.settings.max_fetches_per_round),
            fetch_timeout_seconds=(
                self.settings.firecrawl_http_timeout_seconds + self.settings.fetch_timeout_seconds + 4
                if self.settings.firecrawl_endpoint
                else self.settings.fetch_timeout_seconds + 1
            ),
            per_domain_concurrency=1,
            per_domain_delay_ms=300,
            max_fetches_per_round=self.settings.max_fetches_per_round,
        )
        coordinator = FetchCoordinator(self.fetch_one, limits)
        outcomes = await coordinator.fetch_many([result.url for result in selected])
        documents = {outcome.url: outcome.value for outcome in outcomes if outcome.status == "success"}
        enriched: list[SearchResult] = []
        for result in results:
            document = documents.get(result.url)
            if not isinstance(document, FetchedDocument):
                enriched.append(result)
                continue
            final_url = document.final_url or result.url
            host = (urlsplit(final_url).hostname or "").casefold()
            source_role = "primary_official" if host in authority_hosts or host.endswith((".gov.cn", ".gov", ".edu.cn", ".edu")) else result.source_role
            enriched.append(
                replace(
                    result,
                    url=final_url,
                    title=document.title or result.title,
                    publisher=result.publisher or host,
                    published_at=result.published_at or document.published_at,
                    content=document.content if document.status == "success" else None,
                    content_status="fetched" if document.status == "success" else document.status,
                    source_role=source_role,
                    fetch_engine=document.engine,
                    fetch_status_code=document.status_code,
                    cache_state=document.cache_state,
                )
            )
        return enriched
