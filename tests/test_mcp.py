from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_handshake_lists_tools_and_reads_resource(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["CNWS_DATA_DIR"] = directory
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "cn_web_search_mcp"],
                env=environment,
            )
            async with stdio_client(parameters) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    self.assertEqual(
                        {"research_start", "research_status", "research_result", "research_cancel"},
                        names,
                    )
                    resource = await session.read_resource("cnws://config/public")
                    payload = json.loads(resource.contents[0].text)
                    self.assertIn("web_search_backend", payload)
                    self.assertIn("max_job_workers", payload)


if __name__ == "__main__":
    unittest.main()
