from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CN Web Search MCP server")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    if args.transport:
        os.environ["CNWS_MCP_TRANSPORT"] = args.transport
    if args.host:
        os.environ["CNWS_MCP_HOST"] = args.host
    if args.port:
        os.environ["CNWS_MCP_PORT"] = str(args.port)

    from .server import run

    run()


if __name__ == "__main__":
    main()
