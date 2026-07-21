from __future__ import annotations

import unittest

from cn_web_search_mcp.core.sources import RuntimeCoverageRegistry, SourceRegistry, SourceRouter


class SourceRoutingTests(unittest.TestCase):
    def setUp(self):
        self.registry = SourceRegistry.load_default()
        self.router = SourceRouter.load_default(self.registry)

    def test_sports_query_routes_vertical_sources_after_full_scan(self):
        plan = self.router.plan("帮我查一下最新的世界杯赛程")
        source_ids = {route.source_id for route in plan.routes}
        self.assertIn("sports", plan.intents)
        self.assertIn("dongqiudi", source_ids)
        self.assertIn("sport", source_ids)
        self.assertEqual(plan.evaluated_sources, len(self.registry.all()))
        self.assertTrue(plan.catalog_scan_completed)
        self.assertEqual(plan.discovery_policy, "mandatory-four-source-set-remains-independent")

    def test_explicit_entity_match_outranks_generic_finance_preference(self):
        plan = self.router.plan("查询央行最新 LPR 政策")
        routes = {route.source_id: route for route in plan.routes}
        self.assertGreater(routes["pbc"].score, routes["eastmoney"].score)
        self.assertEqual(routes["pbc"].role, "verification")

    def test_coverage_keeps_declared_and_executable_separate(self):
        coverage = RuntimeCoverageRegistry()
        first = self.registry.get("people")
        endpoint_id = first.endpoints[0].id
        coverage.register("people", [endpoint_id])
        report = coverage.report(self.registry)
        self.assertIn(endpoint_id, report["sources"]["people"]["executable"])
        self.assertGreater(report["declared_endpoint_count"], report["executable_endpoint_count"])


if __name__ == "__main__":
    unittest.main()
