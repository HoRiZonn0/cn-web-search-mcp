"""Compatibility layer for routed catalog adapters and their batch runner."""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import re
from dataclasses import dataclass, field
from time import perf_counter
from urllib.parse import quote_plus
from xml.etree import ElementTree

from .config import Settings
from .core.engines import EngineResponse
from .core.models import Query, SearchResult, StageRecord, StageStatus
from .network import HttpClient, decode_body


def _result_id(engine: str, query_id: str, url: str) -> str:
    digest = hashlib.sha256(f"{engine}\0{query_id}\0{url}".encode()).hexdigest()[:20]
    return f"{engine}-{digest}"


def _plain_text(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def _crossref_date(item: dict) -> str | None:
    for key in ("published-online", "published-print", "published", "issued"):
        parts = item.get(key, {}).get("date-parts", [])
        if not parts or not parts[0]:
            continue
        values = list(parts[0]) + [1, 1]
        return f"{int(values[0]):04d}-{int(values[1]):02d}-{int(values[2]):02d}"
    return None


class CrossrefSearchAdapter:
    name = "crossref_api"
    source_id = "crossref"
    endpoint_ids = {"crossref-works-api"}
    discovery_endpoint_ids: set[str] = set()

    def __init__(self, client: HttpClient, settings: Settings):
        self.client = client
        self.settings = settings

    def search(self, query: Query) -> EngineResponse:
        fields = "DOI,title,URL,published-online,published-print,published,issued,author,publisher,abstract"
        url = (
            "https://api.crossref.org/works?query.bibliographic="
            f"{quote_plus(query.text)}&rows={self.settings.max_results_per_source}&select={fields}"
        )
        try:
            response = self.client.get(url, timeout=self.settings.request_timeout_seconds)
            if not 200 <= response.status_code < 400:
                return EngineResponse(StageStatus.ERROR, error=f"HTTP {response.status_code}")
            payload = json.loads(decode_body(response))
            results: list[SearchResult] = []
            for item in payload.get("message", {}).get("items", []):
                title_values = item.get("title") or []
                title = _plain_text(str(title_values[0])) if title_values else ""
                target = str(item.get("URL") or "").strip()
                if not title or not target:
                    continue
                abstract = _plain_text(str(item.get("abstract") or ""))
                authors = [
                    " ".join(filter(None, [author.get("given"), author.get("family")]))
                    for author in item.get("author", [])[:5]
                ]
                snippet = abstract or "; ".join(value for value in authors if value)
                results.append(
                    SearchResult(
                        result_id=_result_id(self.name, query.id, target),
                        engine=self.name,
                        query_id=query.id,
                        title=title[:500],
                        url=target,
                        snippet=snippet[:1000],
                        publisher=str(item.get("publisher") or "Crossref"),
                        published_at=_crossref_date(item),
                        content=abstract or snippet,
                        content_status="fetched" if abstract or snippet else "not_fetched",
                        source_role="unknown",
                        discovered_by=[self.name],
                        matched_requirement_ids=list(query.requirement_ids),
                        search_channel="structured_source",
                        search_backend="crossref",
                        upstream_engine="crossref",
                    )
                )
            return EngineResponse(StageStatus.SUCCESS if results else StageStatus.EMPTY, results)
        except Exception as exc:
            return EngineResponse(StageStatus.ERROR, error=str(exc))


class ArxivSearchAdapter:
    name = "arxiv_api"
    source_id = "arxiv"
    endpoint_ids = {"arxiv-query-api"}
    discovery_endpoint_ids: set[str] = set()
    _ATOM = "{http://www.w3.org/2005/Atom}"

    def __init__(self, client: HttpClient, settings: Settings):
        self.client = client
        self.settings = settings

    def search(self, query: Query) -> EngineResponse:
        url = (
            "https://export.arxiv.org/api/query?search_query=all:"
            f"{quote_plus(query.text)}&start=0&max_results={self.settings.max_results_per_source}"
        )
        try:
            response = self.client.get(url, timeout=self.settings.request_timeout_seconds)
            if not 200 <= response.status_code < 400:
                return EngineResponse(StageStatus.ERROR, error=f"HTTP {response.status_code}")
            root = ElementTree.fromstring(decode_body(response))
            results: list[SearchResult] = []
            for entry in root.findall(f"{self._ATOM}entry"):
                target = (entry.findtext(f"{self._ATOM}id") or "").strip()
                title = " ".join((entry.findtext(f"{self._ATOM}title") or "").split())
                summary = " ".join((entry.findtext(f"{self._ATOM}summary") or "").split())
                published = (entry.findtext(f"{self._ATOM}published") or "").strip() or None
                if not target or not title:
                    continue
                results.append(
                    SearchResult(
                        result_id=_result_id(self.name, query.id, target),
                        engine=self.name,
                        query_id=query.id,
                        title=title[:500],
                        url=target,
                        snippet=summary[:1000],
                        publisher="arXiv",
                        published_at=published,
                        content=summary,
                        content_status="fetched" if summary else "not_fetched",
                        source_role="primary_official",
                        discovered_by=[self.name],
                        matched_requirement_ids=list(query.requirement_ids),
                        search_channel="structured_source",
                        search_backend="arxiv-api",
                        upstream_engine="arxiv",
                    )
                )
            return EngineResponse(StageStatus.SUCCESS if results else StageStatus.EMPTY, results)
        except Exception as exc:
            return EngineResponse(StageStatus.ERROR, error=str(exc))


class PubMedSearchAdapter:
    """PubMed E-utilities adapter using the public JSON endpoints."""

    name = "pubmed_api"
    source_id = "nih"
    endpoint_ids = {"pubmed-eutils-api"}
    discovery_endpoint_ids: set[str] = set()

    def __init__(self, client: HttpClient, settings: Settings):
        self.client = client
        self.settings = settings

    def search(self, query: Query) -> EngineResponse:
        search_url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&retmode=json&retmax={self.settings.max_results_per_source}"
            f"&term={quote_plus(query.text)}"
        )
        try:
            search_response = self.client.get(
                search_url, timeout=self.settings.request_timeout_seconds
            )
            if not 200 <= search_response.status_code < 400:
                return EngineResponse(
                    StageStatus.ERROR,
                    error=f"HTTP {search_response.status_code}",
                )
            search_payload = json.loads(decode_body(search_response))
            identifiers = [
                str(value)
                for value in search_payload.get("esearchresult", {}).get("idlist", [])
                if str(value).strip()
            ]
            if not identifiers:
                return EngineResponse(StageStatus.EMPTY)

            summary_url = (
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                f"?db=pubmed&retmode=json&id={quote_plus(','.join(identifiers))}"
            )
            summary_response = self.client.get(
                summary_url, timeout=self.settings.request_timeout_seconds
            )
            if not 200 <= summary_response.status_code < 400:
                return EngineResponse(
                    StageStatus.ERROR,
                    error=f"HTTP {summary_response.status_code}",
                )
            payload = json.loads(decode_body(summary_response)).get("result", {})
            results: list[SearchResult] = []
            for identifier in identifiers:
                item = payload.get(identifier, {})
                title = _plain_text(str(item.get("title") or ""))
                if not title:
                    continue
                target = f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/"
                authors = "; ".join(
                    str(author.get("name", "")).strip()
                    for author in item.get("authors", [])[:5]
                    if str(author.get("name", "")).strip()
                )
                results.append(
                    SearchResult(
                        result_id=_result_id(self.name, query.id, target),
                        engine=self.name,
                        query_id=query.id,
                        title=title[:500],
                        url=target,
                        snippet=authors[:1000],
                        publisher=str(item.get("fulljournalname") or "PubMed"),
                        published_at=str(item.get("pubdate") or "").strip() or None,
                        content=authors,
                        content_status="fetched" if authors else "not_fetched",
                        source_role="primary_official",
                        discovered_by=[self.name],
                        matched_requirement_ids=list(query.requirement_ids),
                        search_channel="structured_source",
                        search_backend="pubmed-eutils",
                        upstream_engine="pubmed",
                    )
                )
            return EngineResponse(
                StageStatus.SUCCESS if results else StageStatus.EMPTY,
                results,
            )
        except Exception as exc:
            return EngineResponse(StageStatus.ERROR, error=str(exc))


@dataclass(slots=True)
class StructuredExecution:
    stages: list[StageRecord] = field(default_factory=list)
    results: list[SearchResult] = field(default_factory=list)


def build_structured_adapters(
    selected_source_ids: set[str],
    settings: Settings,
    client: HttpClient,
) -> list:
    adapters = {
        "crossref": CrossrefSearchAdapter(client, settings),
        "arxiv": ArxivSearchAdapter(client, settings),
        "nih": PubMedSearchAdapter(client, settings),
    }
    return [adapter for source_id, adapter in adapters.items() if source_id in selected_source_ids]


def register_structured_adapter_coverage(coverage) -> None:
    coverage.register("crossref", ["crossref-works-api"])
    coverage.register("arxiv", ["arxiv-query-api"])
    coverage.register("nih", ["pubmed-eutils-api"])


async def run_structured_sources(
    adapters: list,
    queries: list[Query],
    *,
    timeout_seconds: float,
    max_concurrency: int = 3,
) -> StructuredExecution:
    """Run any routed catalog adapters with bounded independent failures.

    The historical function name remains public for compatibility; adapters may
    now be direct structured APIs or catalog domain-discovery implementations.
    """
    execution = StructuredExecution()
    if not adapters or not queries:
        return execution
    semaphore = asyncio.Semaphore(max_concurrency)

    async def run(adapter, query):
        started = perf_counter()
        try:
            async with semaphore:
                response = await asyncio.wait_for(
                    asyncio.to_thread(adapter.search, query),
                    timeout=timeout_seconds,
                )
        except (asyncio.TimeoutError, TimeoutError) as exc:
            response = EngineResponse(StageStatus.TIMEOUT, error=str(exc))
        except Exception as exc:
            response = EngineResponse(StageStatus.ERROR, error=str(exc))
        return (
            StageRecord(
                engine=adapter.name,
                status=response.status,
                query_id=query.id,
                result_count=len(response.results),
                elapsed_ms=round((perf_counter() - started) * 1000),
                error=response.error,
            ),
            response.results,
        )

    outcomes = await asyncio.gather(
        *(run(adapter, query) for query in queries for adapter in adapters)
    )
    for stage, results in outcomes:
        execution.stages.append(stage)
        execution.results.extend(results)
    return execution
