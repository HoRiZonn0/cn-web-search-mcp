"""Standard HTTP API for clients that do not speak MCP."""

from .app import create_api_app

__all__ = ["create_api_app"]
