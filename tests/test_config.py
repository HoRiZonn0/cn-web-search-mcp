from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cn_web_search_mcp.config import Settings
from cn_web_search_mcp.server import _StaticTokenVerifier


class ConfigTests(unittest.IsolatedAsyncioTestCase):
    def test_remote_http_requires_token(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "CNWS_DATA_DIR": directory,
                "CNWS_MCP_TRANSPORT": "streamable-http",
                "CNWS_MCP_HOST": "0.0.0.0",
                "CNWS_MCP_BEARER_TOKEN": "",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "requires CNWS_MCP_BEARER_TOKEN"):
                Settings.from_env()

    def test_remote_rest_api_requires_separate_token(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "CNWS_DATA_DIR": directory,
                "CNWS_API_HOST": "0.0.0.0",
                "CNWS_API_BEARER_TOKEN": "",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "requires CNWS_API_BEARER_TOKEN"):
                Settings.from_env()

    def test_commercial_mode_requires_complete_plan_limits(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "CNWS_DATA_DIR": directory,
                "CNWS_COMMERCIAL_MODE": "true",
                "CNWS_CUSTOMER_ID": "customer-a",
                "CNWS_API_BEARER_TOKEN": "secret",
                "CNWS_MONTHLY_CREDIT_QUOTA": "100",
                "CNWS_RATE_LIMIT_PER_MINUTE": "5",
                "CNWS_MAX_ACTIVE_JOBS": "0",
            },
            clear=False,
        ):
            with self.assertRaisesRegex(ValueError, "CNWS_MAX_ACTIVE_JOBS"):
                Settings.from_env()

    async def test_static_token_verifier_uses_exact_token(self):
        verifier = _StaticTokenVerifier("correct-token")
        accepted = await verifier.verify_token("correct-token")
        rejected = await verifier.verify_token("wrong-token")
        self.assertIsNotNone(accepted)
        self.assertIn("cnws:research", accepted.scopes)
        self.assertIsNone(rejected)


if __name__ == "__main__":
    unittest.main()
