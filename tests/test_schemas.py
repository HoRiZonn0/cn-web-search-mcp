from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


class SchemaTests(unittest.TestCase):
    def test_all_json_schemas_are_valid(self):
        schema_dir = Path(__file__).resolve().parents[1] / "schemas"
        schemas = list(schema_dir.glob("*.schema.json"))
        self.assertGreaterEqual(len(schemas), 7)
        for path in schemas:
            with self.subTest(schema=path.name):
                Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
