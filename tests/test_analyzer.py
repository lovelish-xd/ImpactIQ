import json
import unittest
from pathlib import Path

from src.analyzer import analyze
from src.serializer import serialize_analysis, serialize_analysis_json


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = "demo/OrderProcessing"
BASE_REVISION = "02ccdc8"
TARGET_REVISION = "5d26f89"


class AnalyzerTests(unittest.TestCase):
    """Tests for the full analysis pipeline and JSON serialization."""

    @classmethod
    def setUpClass(cls):
        cls.result = analyze(ROOT, PACKAGE_PATH, BASE_REVISION, TARGET_REVISION)
        cls.data = serialize_analysis(cls.result)
        cls.json_str = serialize_analysis_json(cls.result)

    def test_analysis_completes(self):
        self.assertIsNotNone(self.result)

    def test_comparison_identifies_modified_assets(self):
        self.assertGreater(len(self.result.comparison.modified_assets), 0)

    def test_impact_identifies_changed_assets(self):
        self.assertGreater(len(self.result.impact.changed), 0)

    def test_risk_has_score_and_level(self):
        self.assertGreater(self.result.risk.score, 0)
        self.assertTrue(self.result.risk.level)

    def test_recommendations_generated(self):
        self.assertGreater(len(self.result.recommendations), 0)

    # ── JSON structure tests ───────────────────────────────────────

    def test_json_is_valid(self):
        parsed = json.loads(self.json_str)
        self.assertIsInstance(parsed, dict)

    def test_json_roundtrip(self):
        parsed = json.loads(self.json_str)
        self.assertEqual(parsed, self.data)

    def test_json_has_commits(self):
        self.assertIn("commits", self.data)
        self.assertIn("base", self.data["commits"])
        self.assertIn("target", self.data["commits"])

    def test_json_has_analysis(self):
        analysis = self.data["analysis"]
        self.assertIn("id", analysis)
        self.assertIn("title", analysis)
        self.assertIn("status", analysis)
        self.assertIn("baseCommit", analysis)
        self.assertIn("targetCommit", analysis)

    def test_json_has_summary(self):
        summary = self.data["analysis"]["summary"]
        self.assertIn("headline", summary)
        self.assertIn("items", summary)
        self.assertIsInstance(summary["items"], list)

    def test_json_has_affected_assets(self):
        assets = self.data["analysis"]["affectedAssets"]
        self.assertIsInstance(assets, list)
        self.assertGreater(len(assets), 0)
        for asset in assets:
            self.assertIn("name", asset)
            self.assertIn("type", asset)
            self.assertIn("changeType", asset)
            self.assertIn("risk", asset)
            self.assertIn("description", asset)

    def test_json_has_risk(self):
        risk = self.data["analysis"]["risk"]
        self.assertIn("level", risk)
        self.assertIn("score", risk)
        self.assertIn("drivers", risk)
        self.assertIsInstance(risk["drivers"], list)

    def test_json_has_dependencies(self):
        deps = self.data["analysis"]["dependencies"]
        self.assertIn("nodes", deps)
        self.assertIn("edges", deps)
        self.assertIsInstance(deps["nodes"], list)
        self.assertIsInstance(deps["edges"], list)

    def test_json_has_regression_tests(self):
        tests = self.data["analysis"]["regressionTests"]
        self.assertIsInstance(tests, list)
        self.assertGreater(len(tests), 0)
        for test in tests:
            self.assertIn("name", test)
            self.assertIn("priority", test)
            self.assertIn("scenario", test)

    def test_json_has_changes(self):
        changes = self.data["analysis"]["changes"]
        self.assertIsInstance(changes, list)
        self.assertGreater(len(changes), 0)

    def test_json_has_impact(self):
        impact = self.data["analysis"]["impact"]
        self.assertIsInstance(impact, list)
        self.assertGreater(len(impact), 0)

    def test_save_order_db_in_affected_assets(self):
        names = [a["name"] for a in self.data["analysis"]["affectedAssets"]]
        self.assertTrue(
            any("SaveOrderDB" in name for name in names),
            f"SaveOrderDB not in affected assets: {names}",
        )

    def test_customer_email_in_summary(self):
        items = self.data["analysis"]["summary"]["items"]
        self.assertTrue(
            any("customerEmail" in item for item in items),
            f"customerEmail not found in summary items: {items}",
        )

    # ── Same-revision tests ────────────────────────────────────────

    def test_same_revision_produces_empty_analysis(self):
        same = analyze(ROOT, PACKAGE_PATH, BASE_REVISION, BASE_REVISION)
        data = serialize_analysis(same)
        self.assertEqual(data["analysis"]["risk"]["score"], 0)
        self.assertEqual(len(data["analysis"]["affectedAssets"]), 0)
        self.assertEqual(len(data["analysis"]["regressionTests"]), 0)
        self.assertEqual(len(data["analysis"]["changes"]), 0)


if __name__ == "__main__":
    unittest.main()
