"""MCP boundary: four high-level tools and read-only diagnostic resources."""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings

from .config import Settings
from .core.sources import RuntimeCoverageRegistry, SourceRegistry, SourceRouter
from .jobs import JobService
from .search_adapters import register_search_adapter_coverage
from .structured_adapters import register_structured_adapter_coverage


class _StaticTokenVerifier:
    def __init__(self, expected_token: str):
        self.expected_token = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if not secrets.compare_digest(token, self.expected_token):
            return None
        return AccessToken(token=token, client_id="cnws-static-client", scopes=["cnws:research"])


def create_server(settings: Settings | None = None, service: JobService | None = None) -> tuple[FastMCP, JobService]:
    settings = settings or Settings.from_env()
    service = service or JobService(settings)
    source_registry = SourceRegistry.load_default()
    source_router = SourceRouter.load_default(source_registry)
    source_coverage = RuntimeCoverageRegistry()
    register_search_adapter_coverage(source_coverage)
    register_structured_adapter_coverage(source_coverage)
    base_url = f"http://{settings.host}:{settings.port}"
    auth = None
    verifier = None
    if settings.mcp_bearer_token:
        auth = AuthSettings(
            issuer_url=base_url,
            resource_server_url=f"{base_url}/mcp",
            required_scopes=["cnws:research"],
        )
        verifier = _StaticTokenVerifier(settings.mcp_bearer_token)
    mcp = FastMCP(
        "CN Web Search",
        instructions=(
            "Start one autonomous research job, poll it silently, then answer only from the final evidence. "
            "Do not expose intermediate search progress to the user."
        ),
        host=settings.host,
        port=settings.port,
        json_response=True,
        auth=auth,
        token_verifier=verifier,
    )

    @mcp.tool()
    def research_start(
        question: str,
        requirements: list[str] | None = None,
        cutoff_at: str | None = None,
        timezone: str = "Asia/Shanghai",
        profile: str = "balanced",
        max_rounds: int = 3,
    ) -> dict[str, Any]:
        """Start autonomous web research and return a durable job ID immediately."""

        return service.start(
            {
                "question": question,
                "requirements": requirements or [],
                "cutoff_at": cutoff_at,
                "timezone": timezone,
                "profile": profile,
                "max_rounds": max_rounds,
            }
        )

    @mcp.tool()
    def research_status(job_id: str) -> dict[str, Any]:
        """Read compact machine-oriented progress for a research job; poll without narrating it."""

        return service.status(job_id)

    @mcp.tool()
    def research_result(job_id: str) -> dict[str, Any]:
        """Return the final answer context and evidence when a research job reaches a terminal state."""

        return service.result(job_id)

    @mcp.tool()
    def research_cancel(job_id: str) -> dict[str, Any]:
        """Request cooperative cancellation of a queued or running research job."""

        return service.cancel(job_id)

    @mcp.resource("cnws://jobs/{job_id}/status")
    def job_status_resource(job_id: str) -> str:
        """Read durable job status as JSON."""

        return json.dumps(service.status(job_id), ensure_ascii=False, indent=2)

    @mcp.resource("cnws://jobs/{job_id}/result")
    def job_result_resource(job_id: str) -> str:
        """Read the public result as JSON."""

        return json.dumps(service.result(job_id), ensure_ascii=False, indent=2)

    @mcp.resource("cnws://jobs/{job_id}/evidence")
    def job_evidence_resource(job_id: str) -> str:
        """Read the complete local evidence artifact for diagnostics and evaluation."""

        payload = service.store.read_artifact(job_id, "final-evidence.json")
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @mcp.resource("cnws://config/public")
    def public_config_resource() -> str:
        """Read non-secret runtime limits and selected backends."""

        return json.dumps(
            {
                "web_search_backend": settings.web_search_backend,
                "searxng_configured": bool(settings.searxng_endpoint),
                "firecrawl_configured": bool(settings.firecrawl_endpoint),
                "proxy_configured": bool(settings.proxy_url),
                "request_timeout_seconds": settings.request_timeout_seconds,
                "fetch_timeout_seconds": settings.fetch_timeout_seconds,
                "max_results_per_source": settings.max_results_per_source,
                "max_fetches_per_round": settings.max_fetches_per_round,
                "max_job_workers": settings.max_job_workers,
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.resource("cnws://sources/catalog")
    def source_catalog_resource() -> str:
        """Read catalog completeness without exposing the full knowledge base."""

        return json.dumps(source_registry.full_scan_report(), ensure_ascii=False, indent=2)

    @mcp.resource("cnws://sources/coverage")
    def source_coverage_resource() -> str:
        """Distinguish declared endpoints from executable runtime adapters."""

        return json.dumps(source_coverage.report(source_registry), ensure_ascii=False, indent=2)

    @mcp.resource("cnws://sources/route/{query}")
    def source_route_resource(query: str) -> str:
        """Preview intent-specific source hints; mandatory four-source discovery is separate."""

        plan = source_router.plan(query)
        return json.dumps(
            {
                "question": plan.question,
                "intents": plan.intents,
                "routes": [
                    {
                        "source_id": item.source_id,
                        "role": item.role,
                        "intents": item.intents,
                        "score": item.score,
                        "reasons": item.reasons,
                    }
                    for item in plan.routes
                ],
                "evaluated_sources": plan.evaluated_sources,
                "catalog_scan_completed": plan.catalog_scan_completed,
                "discovery_policy": plan.discovery_policy,
            },
            ensure_ascii=False,
            indent=2,
        )

    return mcp, service


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    server, service = create_server(settings)
    try:
        server.run(transport=settings.transport)
    finally:
        service.close()
