"""Environment-backed configuration for the autonomous MCP service."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    data_dir: Path
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8765
    api_host: str = "127.0.0.1"
    api_port: int = 8766
    api_bearer_token: str | None = None
    api_sync_timeout_seconds: float = 120.0
    commercial_mode: bool = False
    customer_id: str = "local"
    customer_plan: str = "developer"
    monthly_credit_quota: int = 0
    rate_limit_per_minute: int = 0
    max_active_jobs: int = 0
    user_agent: str = DEFAULT_USER_AGENT
    proxy_url: str | None = None
    searxng_endpoint: str | None = None
    searxng_engines: str | None = None
    firecrawl_endpoint: str | None = None
    firecrawl_api_key: str | None = None
    web_search_backend: str = "auto"
    request_timeout_seconds: float = 10.0
    fetch_timeout_seconds: float = 18.0
    max_response_bytes: int = 2_000_000
    max_results_per_source: int = 8
    max_fetches_per_round: int = 12
    max_job_workers: int = 2
    allow_private_networks: bool = False
    cache_ttl_seconds: int = 3600
    mcp_bearer_token: str | None = None
    firecrawl_http_timeout_seconds: float = 4.0

    @classmethod
    def from_env(cls) -> "Settings":
        default_dir = Path.home() / ".cn-web-search-mcp"
        settings = cls(
            data_dir=Path(os.getenv("CNWS_DATA_DIR", str(default_dir))).expanduser().resolve(),
            transport=os.getenv("CNWS_MCP_TRANSPORT", "stdio"),
            host=os.getenv("CNWS_MCP_HOST", "127.0.0.1"),
            port=int(os.getenv("CNWS_MCP_PORT", "8765")),
            api_host=os.getenv("CNWS_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("CNWS_API_PORT", "8766")),
            api_bearer_token=os.getenv("CNWS_API_BEARER_TOKEN") or None,
            api_sync_timeout_seconds=float(
                os.getenv("CNWS_API_SYNC_TIMEOUT_SECONDS", "120")
            ),
            commercial_mode=_bool("CNWS_COMMERCIAL_MODE", False),
            customer_id=os.getenv("CNWS_CUSTOMER_ID", "local").strip().casefold(),
            customer_plan=os.getenv("CNWS_CUSTOMER_PLAN", "developer").strip(),
            monthly_credit_quota=int(
                os.getenv("CNWS_MONTHLY_CREDIT_QUOTA", "0")
            ),
            rate_limit_per_minute=int(
                os.getenv("CNWS_RATE_LIMIT_PER_MINUTE", "0")
            ),
            max_active_jobs=int(os.getenv("CNWS_MAX_ACTIVE_JOBS", "0")),
            user_agent=os.getenv("CNWS_USER_AGENT", DEFAULT_USER_AGENT),
            proxy_url=os.getenv("CNWS_PROXY_URL") or None,
            searxng_endpoint=os.getenv("CNWS_SEARXNG_ENDPOINT") or None,
            searxng_engines=os.getenv("CNWS_SEARXNG_ENGINES") or None,
            firecrawl_endpoint=os.getenv("CNWS_FIRECRAWL_ENDPOINT") or None,
            firecrawl_api_key=os.getenv("CNWS_FIRECRAWL_API_KEY") or None,
            web_search_backend=os.getenv("CNWS_WEB_SEARCH_BACKEND", "auto").casefold(),
            request_timeout_seconds=float(os.getenv("CNWS_REQUEST_TIMEOUT_SECONDS", "10")),
            fetch_timeout_seconds=float(os.getenv("CNWS_FETCH_TIMEOUT_SECONDS", "18")),
            max_response_bytes=int(os.getenv("CNWS_MAX_RESPONSE_BYTES", "2000000")),
            max_results_per_source=int(os.getenv("CNWS_MAX_RESULTS_PER_SOURCE", "8")),
            max_fetches_per_round=int(os.getenv("CNWS_MAX_FETCHES_PER_ROUND", "12")),
            max_job_workers=int(os.getenv("CNWS_MAX_JOB_WORKERS", "2")),
            allow_private_networks=_bool("CNWS_ALLOW_PRIVATE_NETWORKS", False),
            cache_ttl_seconds=int(os.getenv("CNWS_CACHE_TTL_SECONDS", "3600")),
            mcp_bearer_token=os.getenv("CNWS_MCP_BEARER_TOKEN") or None,
            firecrawl_http_timeout_seconds=float(os.getenv("CNWS_FIRECRAWL_HTTP_TIMEOUT_SECONDS", "4")),
        )
        if settings.transport not in {"stdio", "streamable-http"}:
            raise ValueError("CNWS_MCP_TRANSPORT must be stdio or streamable-http")
        if settings.web_search_backend not in {"auto", "searxng", "duckduckgo"}:
            raise ValueError("CNWS_WEB_SEARCH_BACKEND must be auto, searxng, or duckduckgo")
        if not 1 <= settings.api_port <= 65535:
            raise ValueError("CNWS_API_PORT must be between 1 and 65535")
        if settings.api_sync_timeout_seconds <= 0:
            raise ValueError("CNWS_API_SYNC_TIMEOUT_SECONDS must be positive")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", settings.customer_id):
            raise ValueError(
                "CNWS_CUSTOMER_ID must be 2-64 lowercase letters, numbers, _ or -"
            )
        if settings.commercial_mode:
            if not settings.api_bearer_token:
                raise ValueError(
                    "CNWS_COMMERCIAL_MODE requires CNWS_API_BEARER_TOKEN"
                )
            if settings.monthly_credit_quota < 1:
                raise ValueError(
                    "CNWS_COMMERCIAL_MODE requires a positive "
                    "CNWS_MONTHLY_CREDIT_QUOTA"
                )
            if settings.rate_limit_per_minute < 1:
                raise ValueError(
                    "CNWS_COMMERCIAL_MODE requires a positive "
                    "CNWS_RATE_LIMIT_PER_MINUTE"
                )
            if settings.max_active_jobs < 1:
                raise ValueError(
                    "CNWS_COMMERCIAL_MODE requires a positive "
                    "CNWS_MAX_ACTIVE_JOBS"
                )
        if (
            settings.api_host not in {"127.0.0.1", "localhost", "::1"}
            and not settings.api_bearer_token
        ):
            raise ValueError(
                "non-loopback REST API binding requires CNWS_API_BEARER_TOKEN"
            )
        if (
            settings.transport == "streamable-http"
            and settings.host not in {"127.0.0.1", "localhost", "::1"}
            and not settings.mcp_bearer_token
        ):
            raise ValueError("non-loopback HTTP binding requires CNWS_MCP_BEARER_TOKEN")
        return settings

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "artifacts").mkdir(parents=True, exist_ok=True)
