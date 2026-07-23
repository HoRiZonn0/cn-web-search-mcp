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
                    catalog_resource = await session.read_resource("cnws://sources/catalog")
                    catalog = json.loads(catalog_resource.contents[0].text)
                    self.assertTrue(catalog["validation_completed"])
                    self.assertEqual(catalog["declared_sources"], 108)
                    coverage_resource = await session.read_resource("cnws://sources/coverage")
                    coverage = json.loads(coverage_resource.contents[0].text)
                    self.assertEqual(coverage["executable_endpoint_count"], 7)
                    self.assertGreater(coverage["discovery_endpoint_count"], 90)
                    self.assertIn("pubmed-eutils-api", coverage["sources"]["nih"]["executable"])


if __name__ == "__main__":
    unittest.main()
