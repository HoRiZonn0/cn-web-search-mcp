"""FastAPI gateway sharing the MCP server's JobService."""

from __future__ import annotations

import asyncio
import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .. import __version__
from ..config import Settings
from ..jobs import JobService
from .models import ResearchRequest


_TERMINAL = {"completed", "unresolvable", "failed", "cancelled"}
_bearer = HTTPBearer(auto_error=False)


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc).strip("'"))


def create_api_app(
    settings: Settings | None = None,
    service: JobService | None = None,
) -> FastAPI:
    """Create a REST application without duplicating research orchestration."""

    settings = settings or Settings.from_env()
    if (
        settings.api_host not in {"127.0.0.1", "localhost", "::1"}
        and not settings.api_bearer_token
    ):
        raise ValueError(
            "non-loopback REST API binding requires CNWS_API_BEARER_TOKEN"
        )
    owns_service = service is None
    service = service or JobService(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if owns_service:
            service.close()

    app = FastAPI(
        title="CN Web Search API",
        version=__version__,
        description=(
            "Asynchronous Chinese web research API backed by the same "
            "JobService used by the MCP server."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.job_service = service

    def authorize(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(_bearer),
        ] = None,
    ) -> None:
        expected = settings.api_bearer_token
        if expected is None:
            return
        if (
            credentials is None
            or credentials.scheme.casefold() != "bearer"
            or not secrets.compare_digest(credentials.credentials, expected)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    auth = Depends(authorize)

    @app.get("/healthz", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/v1/research",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[auth],
        tags=["research"],
    )
    def start_research(request: ResearchRequest) -> dict:
        return service.start(request.model_dump(mode="json"))

    @app.get(
        "/v1/research/{job_id}",
        dependencies=[auth],
        tags=["research"],
    )
    def research_status(job_id: str) -> dict:
        try:
            return service.status(job_id)
        except KeyError as exc:
            raise _not_found(exc) from exc

    @app.get(
        "/v1/research/{job_id}/result",
        dependencies=[auth],
        tags=["research"],
    )
    def research_result(job_id: str):
        try:
            payload = service.result(job_id)
        except KeyError as exc:
            raise _not_found(exc) from exc
        response_status = (
            status.HTTP_200_OK
            if payload["status"] in _TERMINAL
            else status.HTTP_202_ACCEPTED
        )
        return JSONResponse(payload, status_code=response_status)

    @app.delete(
        "/v1/research/{job_id}",
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[auth],
        tags=["research"],
    )
    def cancel_research(job_id: str) -> dict:
        try:
            return service.cancel(job_id)
        except KeyError as exc:
            raise _not_found(exc) from exc

    @app.post(
        "/v1/research/sync",
        dependencies=[auth],
        tags=["research"],
    )
    async def research_sync(request: ResearchRequest):
        started = service.start(request.model_dump(mode="json"))
        job_id = started["job_id"]
        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.api_sync_timeout_seconds
        while loop.time() < deadline:
            payload = service.result(job_id)
            if payload["status"] in _TERMINAL:
                return payload
            await asyncio.sleep(0.25)
        return JSONResponse(
            {
                "job_id": job_id,
                "status": service.status(job_id)["status"],
                "result": None,
                "message": "synchronous wait timed out; continue polling the job",
            },
            status_code=status.HTTP_202_ACCEPTED,
        )

    return app
