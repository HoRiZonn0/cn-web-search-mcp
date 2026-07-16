"""Concrete autonomous search adapters for the mandatory four-source set."""

from __future__ import annotations

import hashlib
import json
import re
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlsplit
from xml.etree import ElementTree

from .config import Settings
from .core.engines import EngineResponse
from .core.models import Query, SearchResult, StageStatus
from .network import HttpClient, decode_body


_BLOCK_MARKERS = (
    "访问过于频繁",
    "请输入验证码",
    "安全验证",
    "captcha",
    "robot check",
    "异常流量",
)


def _iso_date(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        return parsedate_to_datetime(text).isoformat()
    except (TypeError, ValueError):
        return text


class _AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current_url: str | None = None
        self.current_text: list[str] = []
        self.items: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.casefold() != "a":
            return
        values = {key.casefold(): value for key, value in attrs if value}
        self.current_url = values.get("data-mdurl") or values.get("data-url") or values.get("href")
        self.current_text = []

    def handle_data(self, data: str):
        if self.current_url:
            self.current_text.append(data)

    def handle_endtag(self, tag: str):
        if tag.casefold() == "a" and self.current_url:
            text = " ".join("".join(self.current_text).split())
            if text:
                self.items.append((self.current_url, text))
            self.current_url = None
            self.current_text = []


def _result_id(engine: str, query_id: str, url: str) -> str:
    digest = hashlib.sha256(f"{engine}\0{query_id}\0{url}".encode()).hexdigest()[:20]
    return f"{engine}-{digest}"


def _unwrap_url(raw: str, base_url: str) -> str:
    value = urljoin(base_url, raw.strip())
    parsed = urlsplit(value)
    query = parse_qs(parsed.query)
    for key in ("uddg", "url", "target", "u"):
        candidate = query.get(key, [None])[0]
        if candidate and unquote(candidate).startswith(("http://", "https://")):
            return unquote(candidate)
    return value


def _html_results(
    html: str,
    *,
    base_url: str,
    engine: str,
    backend: str,
    query: Query,
    limit: int,
) -> list[SearchResult]:
    parser = _AnchorParser()
    parser.feed(html)
    internal_host = (urlsplit(base_url).hostname or "").casefold()
    seen: set[str] = set()
    results: list[SearchResult] = []
    for raw_url, title in parser.items:
        url = _unwrap_url(raw_url, base_url)
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            continue
        if parsed.hostname.casefold() == internal_host and not re.search(r"/(link|redirect)", parsed.path):
            continue
        if len(title) < 3 or url in seen:
            continue
        seen.add(url)
        results.append(
            SearchResult(
                result_id=_result_id(engine, query.id, url),
                engine=engine,
                query_id=query.id,
                title=title[:500],
                url=url,
                discovered_by=[engine],
                matched_requirement_ids=list(query.requirement_ids),
                search_channel=engine,
                search_backend=backend,
            )
        )
        if len(results) >= limit:
            break
    return results


def _status(code: int, body: str, results: list[SearchResult]) -> StageStatus:
    normalized = body.casefold()
    if code in {401, 403, 429} or any(marker in normalized for marker in _BLOCK_MARKERS):
        return StageStatus.BLOCKED
    if code < 200 or code >= 400:
        return StageStatus.ERROR
    return StageStatus.SUCCESS if results else StageStatus.EMPTY


class HtmlSearchAdapter:
    def __init__(self, name: str, endpoint: str, client: HttpClient, settings: Settings):
        self.name = name
        self.endpoint = endpoint
        self.client = client
        self.settings = settings

    def search(self, query: Query) -> EngineResponse:
        url = self.endpoint.format(query=quote_plus(query.text))
        try:
            response = self.client.get(url, timeout=self.settings.request_timeout_seconds)
            body = decode_body(response)
            results = _html_results(
                body,
                base_url=response.url,
                engine=self.name,
                backend=self.name,
                query=query,
                limit=self.settings.max_results_per_source,
            )
            status = _status(response.status_code, body, results)
            return EngineResponse(status=status, results=results, error=None if status in {StageStatus.SUCCESS, StageStatus.EMPTY} else f"HTTP {response.status_code}")
        except Exception as exc:
            return EngineResponse(StageStatus.ERROR, error=str(exc))


class BingRssAdapter:
    name = "bing_rss"

    def __init__(self, client: HttpClient, settings: Settings):
        self.client = client
        self.settings = settings

    def search(self, query: Query) -> EngineResponse:
        url = f"https://cn.bing.com/search?format=rss&q={quote_plus(query.text)}"
        try:
            response = self.client.get(url, timeout=self.settings.request_timeout_seconds)
            body = decode_body(response)
            results: list[SearchResult] = []
            if 200 <= response.status_code < 400:
                root = ElementTree.fromstring(body)
                for item in root.findall(".//item")[: self.settings.max_results_per_source]:
                    target = (item.findtext("link") or "").strip()
                    title = " ".join((item.findtext("title") or "").split())
                    if not target or not title:
                        continue
                    results.append(
                        SearchResult(
                            result_id=_result_id(self.name, query.id, target),
                            engine=self.name,
                            query_id=query.id,
                            title=title,
                            url=target,
                            snippet=" ".join((item.findtext("description") or "").split()),
                            published_at=_iso_date(item.findtext("pubDate")),
                            discovered_by=[self.name],
                            matched_requirement_ids=list(query.requirement_ids),
                            search_channel=self.name,
                            search_backend="bing-rss",
                            upstream_engine="bing",
                        )
                    )
            status = _status(response.status_code, body, results)
            return EngineResponse(status, results, None if status in {StageStatus.SUCCESS, StageStatus.EMPTY} else f"HTTP {response.status_code}")
        except Exception as exc:
            return EngineResponse(StageStatus.ERROR, error=str(exc))


class WebSearchAdapter:
    name = "web_search"

    def __init__(self, client: HttpClient, settings: Settings):
        self.client = client
        self.settings = settings

    @property
    def backend(self) -> str:
        if self.settings.web_search_backend == "auto":
            return "searxng" if self.settings.searxng_endpoint else "duckduckgo"
        return self.settings.web_search_backend

    def search(self, query: Query) -> EngineResponse:
        return self._searxng(query) if self.backend == "searxng" else self._duckduckgo(query)

    def _searxng(self, query: Query) -> EngineResponse:
        if not self.settings.searxng_endpoint:
            return EngineResponse(StageStatus.ERROR, error="CNWS_SEARXNG_ENDPOINT is not configured")
        endpoint = self.settings.searxng_endpoint.rstrip("/") + "/search"
        url = f"{endpoint}?q={quote_plus(query.text)}&format=json&categories=general"
        if self.settings.searxng_engines:
            url += f"&engines={quote_plus(self.settings.searxng_engines)}"
        try:
            response = self.client.get(url, timeout=self.settings.request_timeout_seconds, trusted_network=True)
            payload = json.loads(decode_body(response)) if response.body else {}
            results: list[SearchResult] = []
            for item in payload.get("results", [])[: self.settings.max_results_per_source]:
                target = str(item.get("url", "")).strip()
                title = " ".join(str(item.get("title", "")).split())
                if not target or not title:
                    continue
                upstream = item.get("engines") or item.get("engine") or ""
                if isinstance(upstream, list):
                    upstream = ",".join(str(value) for value in upstream)
                results.append(
                    SearchResult(
                        result_id=_result_id(self.name, query.id, target),
                        engine=self.name,
                        query_id=query.id,
                        title=title,
                        url=target,
                        snippet=" ".join(str(item.get("content", "")).split()),
                        published_at=_iso_date(item.get("publishedDate") or item.get("published_at")),
                        discovered_by=[self.name],
                        matched_requirement_ids=list(query.requirement_ids),
                        search_channel=self.name,
                        search_backend="searxng",
                        upstream_engine=str(upstream),
                    )
                )
            status = _status(response.status_code, json.dumps(payload, ensure_ascii=False), results)
            return EngineResponse(status, results, None if status in {StageStatus.SUCCESS, StageStatus.EMPTY} else f"HTTP {response.status_code}")
        except Exception as exc:
            return EngineResponse(StageStatus.ERROR, error=str(exc))

    def _duckduckgo(self, query: Query) -> EngineResponse:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query.text)}"
        try:
            response = self.client.get(url, timeout=self.settings.request_timeout_seconds)
            body = decode_body(response)
            results = _html_results(
                body,
                base_url=response.url,
                engine=self.name,
                backend="duckduckgo-html",
                query=query,
                limit=self.settings.max_results_per_source,
            )
            for result in results:
                result.upstream_engine = "duckduckgo"
            status = _status(response.status_code, body, results)
            return EngineResponse(status, results, None if status in {StageStatus.SUCCESS, StageStatus.EMPTY} else f"HTTP {response.status_code}")
        except Exception as exc:
            return EngineResponse(StageStatus.ERROR, error=str(exc))


def build_search_adapters(settings: Settings, client: HttpClient | None = None):
    client = client or HttpClient(settings)
    return [
        HtmlSearchAdapter("360", "https://www.so.com/s?q={query}", client, settings),
        HtmlSearchAdapter("sogou", "https://www.sogou.com/web?query={query}", client, settings),
        BingRssAdapter(client, settings),
        WebSearchAdapter(client, settings),
    ]
