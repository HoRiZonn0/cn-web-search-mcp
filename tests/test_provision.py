from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cn_web_search_mcp.provision import ProvisionRequest, provision_customer


class ProvisionTests(unittest.TestCase):
    def test_generates_isolated_customer_bundle_without_secret_in_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "customer-a"
            result = provision_customer(
                ProvisionRequest(
                    customer_id="customer-a",
                    output_dir=output,
                    plan="starter",
                    monthly_credit_quota=500,
                    public_port=9001,
                    api_base_url="https://customer-a.example.com",
                )
            )
            environment = (output / "customer.env").read_text(encoding="utf-8")
            manifest = (output / "customer.json").read_text(encoding="utf-8")
            operations = (output / "OPERATIONS.txt").read_text(encoding="utf-8")
            compose = (output / "compose.yaml").read_text(encoding="utf-8")

        self.assertTrue(result["api_key"].startswith("sk_cnws_live_"))
        self.assertIn(result["api_key"], environment)
        self.assertNotIn(result["api_key"], manifest)
        self.assertNotIn(result["api_key"], operations)
        self.assertIn("CNWS_COMMERCIAL_MODE", compose)
        self.assertIn("CNWS_MONTHLY_CREDIT_QUOTA=500", environment)
        self.assertIn("CNWS_PUBLIC_PORT=9001", environment)

    def test_refuses_to_overwrite_existing_customer_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "customer-a"
            request = ProvisionRequest(
                customer_id="customer-a",
                output_dir=output,
            )
            provision_customer(request)
            with self.assertRaises(FileExistsError):
                provision_customer(request)

    def test_rejects_unsafe_customer_id(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "customer_id"):
                provision_customer(
                    ProvisionRequest(
                        customer_id="../escape",
                        output_dir=Path(directory) / "bad",
                    )
                )


if __name__ == "__main__":
    unittest.main()
