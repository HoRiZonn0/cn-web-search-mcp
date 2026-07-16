from __future__ import annotations

import argparse
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def probe(url: str) -> None:
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            print(
                json.dumps(
                    {
                        "server": initialized.serverInfo.name,
                        "version": initialized.serverInfo.version,
                        "tools": [tool.name for tool in tools.tools],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe a Streamable HTTP CN Web Search MCP server")
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:8765/mcp")
    args = parser.parse_args()
    asyncio.run(probe(args.url))


if __name__ == "__main__":
    main()
