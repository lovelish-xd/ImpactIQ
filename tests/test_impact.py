import unittest
from pathlib import Path

from src.comparison import compare_revisions
from src.dependency import build_dependency_graph
from src.impact import ImpactType, analyze_impact
from src.parser import parse_package


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "OrderProcessing"
BASE_REVISION = "02ccdc8"
TARGET_REVISION = "5d26f89"
PACKAGE_PATH = "demo/OrderProcessing"


class ImpactAnalysisTests(unittest.TestCase):
    """Tests for deterministic impact analysis on the customerEmail change."""

    @classmethod
    def setUpClass(cls):
        cls.comparison = compare_revisions(ROOT, PACKAGE_PATH, BASE_REVISION, TARGET_REVISION)
        cls.graph = build_dependency_graph(
            cls.comparison.target_assets,
            changes=cls.comparison.changes,
        )
        cls.result = analyze_impact(cls.graph)

    def test_save_order_db_is_changed(self):
        changed_ids = {a.asset_id for a in self.result.changed}
        self.assertIn("OrderProcessing.orderProcessing.adapters:SaveOrderDB", changed_ids)

    def test_save_order_is_changed(self):
        changed_ids = {a.asset_id for a in self.result.changed}
        self.assertIn("OrderProcessing.orderProcessing.services:SaveOrder", changed_ids)

    def test_order_processing_is_directly_affected(self):
        """OrderProcessing invokes SaveOrder, which is changed."""
        directly_ids = {a.asset_id for a in self.result.directly_affected}
        self.assertIn(
            "OrderProcessing.orderProcessing.services:OrderProcessing",
            directly_ids,
        )

    def test_directly_affected_has_distance_1(self):
        op = next(
            a for a in self.result.directly_affected
            if a.asset_id == "OrderProcessing.orderProcessing.services:OrderProcessing"
        )
        self.assertEqual(op.distance, 1)

    def test_scheduler_is_transitively_affected(self):
        """scheduler invokes OrderProcessing which invokes SaveOrder."""
        transitive_ids = {a.asset_id for a in self.result.transitively_affected}
        self.assertIn("OrderProcessing.orderProcessing:scheduler", transitive_ids)

    def test_scheduler_has_distance_2(self):
        sched = next(
            a for a in self.result.transitively_affected
            if a.asset_id == "OrderProcessing.orderProcessing:scheduler"
        )
        self.assertEqual(sched.distance, 2)

    def test_unrelated_assets_are_not_affected(self):
        """ValidateOrder has no dependency path to SaveOrderDB or SaveOrder."""
        all_ids = {a.asset_id for a in self.result.all_impacted}
        self.assertNotIn(
            "OrderProcessing.orderProcessing.services:ValidateOrder",
            all_ids,
        )
        self.assertNotIn(
            "OrderProcessing.orderProcessing.services:GetCustomer",
            all_ids,
        )

    def test_changed_assets_have_evidence(self):
        for changed in self.result.changed:
            self.assertGreater(len(changed.evidence), 0, changed.asset_id)

    def test_same_revision_no_impact(self):
        no_change = compare_revisions(ROOT, PACKAGE_PATH, BASE_REVISION, BASE_REVISION)
        graph = build_dependency_graph(no_change.target_assets, changes=no_change.changes)
        result = analyze_impact(graph)
        self.assertEqual(result.changed, ())
        self.assertEqual(result.directly_affected, ())
        self.assertEqual(result.transitively_affected, ())

    def test_all_impacted_property(self):
        total = len(self.result.all_impacted)
        parts = (
            len(self.result.changed)
            + len(self.result.directly_affected)
            + len(self.result.transitively_affected)
        )
        self.assertEqual(total, parts)

    def test_external_nodes_are_not_affected(self):
        all_ids = {a.asset_id for a in self.result.all_impacted}
        self.assertNotIn("pub.flow:getLastError", all_ids)
        self.assertNotIn("pub.math:addFloats", all_ids)


if __name__ == "__main__":
    unittest.main()
