"""Provision a self-contained dedicated customer deployment bundle."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

from . import __version__


_CUSTOMER_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


@dataclass(frozen=True, slots=True)
class ProvisionRequest:
    customer_id: str
    output_dir: Path
    plan: str = "starter"
    monthly_credit_quota: int = 1_000
    rate_limit_per_minute: int = 5
    max_active_jobs: int = 2
    max_job_workers: int = 2
    public_port: int = 8766
    bind_address: str = "127.0.0.1"
    image: str = f"cn-web-search-mcp:{__version__}"
    api_base_url: str | None = None


def _validate(request: ProvisionRequest) -> None:
    if not _CUSTOMER_ID.fullmatch(request.customer_id):
        raise ValueError(
            "customer_id must be 2-64 lowercase letters, numbers, _ or -"
        )
    if not request.plan.strip():
        raise ValueError("plan must not be empty")
    for name, value in (
        ("monthly_credit_quota", request.monthly_credit_quota),
        ("rate_limit_per_minute", request.rate_limit_per_minute),
        ("max_active_jobs", request.max_active_jobs),
        ("max_job_workers", request.max_job_workers),
    ):
        if value < 1:
            raise ValueError(f"{name} must be positive")
    if not 1 <= request.public_port <= 65535:
        raise ValueError("public_port must be between 1 and 65535")


def _write_exclusive(path: Path, content: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def provision_customer(request: ProvisionRequest) -> dict[str, str]:
    """Generate customer secrets and deployment files without overwriting."""

    _validate(request)
    output = request.output_dir.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"customer deployment is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    data_dir = output / "data"
    data_dir.mkdir(exist_ok=False)

    api_key = f"sk_cnws_live_{secrets.token_urlsafe(32)}"
    base_url = request.api_base_url or (
        f"http://{request.bind_address}:{request.public_port}"
    )
    environment = {
        "COMPOSE_PROJECT_NAME": f"cnws-{request.customer_id}",
        "CNWS_IMAGE": request.image,
        "CNWS_BIND_ADDRESS": request.bind_address,
        "CNWS_PUBLIC_PORT": str(request.public_port),
        "CNWS_HOST_DATA_DIR": data_dir.as_posix(),
        "CNWS_API_BEARER_TOKEN": api_key,
        "CNWS_CUSTOMER_ID": request.customer_id,
        "CNWS_CUSTOMER_PLAN": request.plan,
        "CNWS_MONTHLY_CREDIT_QUOTA": str(request.monthly_credit_quota),
        "CNWS_RATE_LIMIT_PER_MINUTE": str(request.rate_limit_per_minute),
        "CNWS_MAX_ACTIVE_JOBS": str(request.max_active_jobs),
        "CNWS_MAX_JOB_WORKERS": str(request.max_job_workers),
        "CNWS_API_SYNC_TIMEOUT_SECONDS": "120",
        "CNWS_PROXY_URL": "",
        "CNWS_SEARXNG_ENDPOINT": "",
        "CNWS_SEARXNG_ENGINES": "",
        "CNWS_FIRECRAWL_ENDPOINT": "",
        "CNWS_FIRECRAWL_API_KEY": "",
    }
    env_path = output / "customer.env"
    _write_exclusive(
        env_path,
        "\n".join(f"{key}={value}" for key, value in environment.items()) + "\n",
    )
    if os.name != "nt":
        env_path.chmod(0o600)

    compose = files("cn_web_search_mcp").joinpath(
        "data/customer-compose.yaml"
    ).read_text(encoding="utf-8")
    _write_exclusive(output / "compose.yaml", compose)

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": 1,
        "service_version": __version__,
        "customer_id": request.customer_id,
        "plan": request.plan,
        "created_at": created_at,
        "api_base_url": base_url,
        "api_key_prefix": api_key[:20],
        "limits": {
            "monthly_credit_quota": request.monthly_credit_quota,
            "rate_limit_per_minute": request.rate_limit_per_minute,
            "max_active_jobs": request.max_active_jobs,
            "max_job_workers": request.max_job_workers,
        },
    }
    _write_exclusive(
        output / "customer.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    _write_exclusive(
        output / "OPERATIONS.txt",
        (
            f"Customer: {request.customer_id}\n"
            f"API base URL: {base_url}\n"
            "Swagger: {0}/docs\n"
            "OpenAPI: {0}/openapi.json\n\n"
            "Start:\n"
            "  docker compose --env-file customer.env up -d\n\n"
            "Status:\n"
            "  docker compose --env-file customer.env ps\n\n"
            "Logs:\n"
            "  docker compose --env-file customer.env logs -f\n\n"
            "Stop:\n"
            "  docker compose --env-file customer.env down\n\n"
            "Keep customer.env private. It contains the customer's API key.\n"
        ).format(base_url),
    )
    return {
        "customer_id": request.customer_id,
        "output_dir": str(output),
        "api_base_url": base_url,
        "api_key": api_key,
        "api_key_prefix": api_key[:20],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision one dedicated CN Web Search customer instance."
    )
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--plan", default="starter")
    parser.add_argument("--monthly-credit-quota", type=int, default=1_000)
    parser.add_argument("--rate-limit-per-minute", type=int, default=5)
    parser.add_argument("--max-active-jobs", type=int, default=2)
    parser.add_argument("--max-job-workers", type=int, default=2)
    parser.add_argument("--public-port", type=int, default=8766)
    parser.add_argument("--bind-address", default="127.0.0.1")
    parser.add_argument("--image", default=f"cn-web-search-mcp:{__version__}")
    parser.add_argument("--api-base-url")
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = provision_customer(
        ProvisionRequest(
            customer_id=args.customer_id,
            output_dir=args.output_dir,
            plan=args.plan,
            monthly_credit_quota=args.monthly_credit_quota,
            rate_limit_per_minute=args.rate_limit_per_minute,
            max_active_jobs=args.max_active_jobs,
            max_job_workers=args.max_job_workers,
            public_port=args.public_port,
            bind_address=args.bind_address,
            image=args.image,
            api_base_url=args.api_base_url,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Store the API key securely; customer.env contains the only deployment copy.")


if __name__ == "__main__":
    main()
