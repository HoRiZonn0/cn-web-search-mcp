"""Command-line entry point for the standard REST API."""

from __future__ import annotations

import uvicorn

from .api import create_api_app
from .config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        create_api_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
