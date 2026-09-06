import unittest
from pathlib import Path

from src.comparison import compare_revisions
from src.dependency import build_dependency_graph
from src.impact import analyze_impact
from src.recommendations import Priority, generate_recommendations


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = "demo/OrderProcessing"
BASE_REVISION = "02ccdc8"
TARGET_REVISION = "5d26f89"


class RecommendationTests(unittest.TestCase):
    """Tests for deterministic regression test recommendations."""

    @classmethod
    def setUpClass(cls):
        cls.comparison = compare_revisions(ROOT, PACKAGE_PATH, BASE_REVISION, TARGET_REVISION)
        cls.graph = build_dependency_graph(
            cls.comparison.target_assets,
            changes=cls.comparison.changes,
        )
        cls.impact = analyze_impact(cls.graph)
        cls.recs = generate_recommendations(cls.comparison, cls.impact, cls.graph)

    def test_recommendations_are_generated(self):
        self.assertGreater(len(self.recs), 0)

    def test_each_recommendation_has_required_fields(self):
        for rec in self.recs:
            self.assertTrue(rec.id)
            self.assertIn(rec.priority, list(Priority))
            self.assertTrue(rec.name)
            self.assertTrue(rec.scenario)
            self.assertGreater(len(rec.related_assets), 0)
            self.assertTrue(rec.reason)

    def test_field_addition_generates_recommendation(self):
        """customerEmail added to SaveOrderDB should produce a test recommendation."""
        names = [r.name for r in self.recs]
        self.assertTrue(
            any("customerEmail" in name for name in names),
            f"No recommendation mentions customerEmail: {names}",
        )

    def test_mapping_addition_generates_recommendation(self):
        """New mapping in SaveOrder should produce a test recommendation."""
        mapping_recs = [r for r in self.recs if "mapping" in r.id.lower() or "mapping" in r.name.lower()]
        self.assertGreater(len(mapping_recs), 0)

    def test_sql_change_generates_recommendation(self):
        """SQL change in SaveOrderDB should produce a test recommendation."""
        sql_recs = [r for r in self.recs if "sql" in r.id.lower() or "database" in r.name.lower()]
        self.assertGreater(len(sql_recs), 0)

    def test_directly_affected_generates_invocation_test(self):
        """OrderProcessing is directly affected and should get an invocation test."""
        invocation_recs = [r for r in self.recs if "invocation" in r.id.lower()]
        related_ids = set()
        for rec in invocation_recs:
            related_ids.update(rec.related_assets)
        self.assertIn(
            "OrderProcessing.orderProcessing.services:OrderProcessing",
            related_ids,
        )

    def test_end_to_end_recommendation_exists(self):
        """There should be an end-to-end smoke test recommendation."""
        e2e_recs = [r for r in self.recs if "e2e" in r.id.lower()]
        self.assertGreater(len(e2e_recs), 0)

    def test_null_handling_recommendation_exists(self):
        """Null/missing field handling should be recommended for added fields."""
        null_recs = [r for r in self.recs if "null" in r.id.lower()]
        self.assertGreater(len(null_recs), 0)

    def test_no_recommendations_for_same_revision(self):
        no_change = compare_revisions(ROOT, PACKAGE_PATH, BASE_REVISION, BASE_REVISION)
        graph = build_dependency_graph(no_change.target_assets, changes=no_change.changes)
        impact = analyze_impact(graph)
        recs = generate_recommendations(no_change, impact, graph)
        self.assertEqual(len(recs), 0)

    def test_recommendations_have_unique_ids(self):
        ids = [r.id for r in self.recs]
        self.assertEqual(len(ids), len(set(ids)))

    def test_priorities_include_high(self):
        priorities = {r.priority for r in self.recs}
        self.assertIn(Priority.HIGH, priorities)


if __name__ == "__main__":
    unittest.main()
