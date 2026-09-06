"""End-to-End tests for the complete ImpactIQ pipeline.

Validates the full chain:
  Git Revision Reader
  → Asset Discovery
  → webMethods Parsers
  → Snapshot Comparison
  → Dependency Graph Construction
  → Impact Traversal
  → Deterministic Risk Scoring
  → Regression Test Recommendations
  → Serialization & JSON Roundtrip
  → Same-Revision Zero-Change Verification
"""

import json
import unittest
from pathlib import Path

from src.analyzer import analyze
from src.comparison import compare_revisions
from src.dependency import EdgeType
from src.impact import ImpactType
from src.models import ChangeType
from src.risk import RiskLevel
from src.serializer import serialize_analysis, serialize_analysis_json

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = "demo/OrderProcessing"
BASE_REVISION = "02ccdc8"
TARGET_REVISION = "5d26f89"


class EndToEndPipelineTests(unittest.TestCase):
    """Full pipeline integration tests comparing 02ccdc8 -> 5d26f89."""

    @classmethod
    def setUpClass(cls):
        cls.result = analyze(
            repository_path=ROOT,
            package_path=PACKAGE_PATH,
            base_revision=BASE_REVISION,
            target_revision=TARGET_REVISION,
        )
        cls.serialized = serialize_analysis(cls.result)
        cls.json_str = serialize_analysis_json(cls.result)

    # ── 1. Semantic Change Detection ──────────────────────────────

    def test_semantic_change_1_saveorderdb_customer_email_input(self):
        """SaveOrderDB has customerEmail added to inputs."""
        field_changes = [
            c for c in self.result.comparison.changes
            if c.change_type == ChangeType.FIELD_ADDED
            and "SaveOrderDB" in c.affected_asset.asset_id
        ]
        self.assertTrue(
            any(c.after and c.after.name == "customerEmail" for c in field_changes),
            f"customerEmail field addition not found in SaveOrderDB: {field_changes}",
        )

    def test_semantic_change_2_saveorder_mapping(self):
        """SaveOrder has mapping OrderDocument/order/customerEmail -> SaveOrderDBInput/customerEmail."""
        mapping_changes = [
            c for c in self.result.comparison.changes
            if c.change_type == ChangeType.MAPPING_ADDED
            and "SaveOrder" in c.affected_asset.asset_id
        ]
        self.assertTrue(
            any(
                c.after
                and "customerEmail" in c.after.source_path
                and "customerEmail" in c.after.target_path
                for c in mapping_changes
            ),
            f"customerEmail mapping addition not found in SaveOrder: {mapping_changes}",
        )

    def test_semantic_change_3_saveorderdb_sql_modified(self):
        """SaveOrderDB query.sql is modified with customer_email column and 6th parameter."""
        sql_changes = [
            c for c in self.result.comparison.changes
            if c.metadata.get("component") == "sql"
            and "SaveOrderDB" in c.affected_asset.asset_id
        ]
        self.assertGreater(len(sql_changes), 0, "No SQL modification detected for SaveOrderDB")
        sql_change = sql_changes[0]
        self.assertIn("customer_email", sql_change.after)
        self.assertNotIn("customer_email", sql_change.before)
        # Verify 6 parameters in target SQL vs 5 in base
        self.assertEqual(sql_change.after.count("?"), 6)
        self.assertEqual(sql_change.before.count("?"), 5)

    # ── 2. Dependency Graph ───────────────────────────────────────

    def test_graph_contains_actual_invocations(self):
        """Verify real repository invocation relationships exist in the graph."""
        edges = self.result.graph.edges
        edge_pairs = {(e.source_id, e.target_id) for e in edges if e.edge_type == EdgeType.INVOCATION}

        # OrderProcessing -> SaveOrder
        self.assertTrue(
            any(
                "OrderProcessing" in src and "SaveOrder" in tgt and "SaveOrderDB" not in tgt
                for src, tgt in edge_pairs
            ),
            "OrderProcessing -> SaveOrder invocation missing",
        )

        # SaveOrder -> SaveOrderDB
        self.assertTrue(
            any(
                "SaveOrder" in src and "SaveOrderDB" in tgt
                for src, tgt in edge_pairs
            ),
            "SaveOrder -> SaveOrderDB invocation missing",
        )

        # GetCustomer -> GetCustomerDB
        self.assertTrue(
            any(
                "GetCustomer" in src and "GetCustomerDB" in tgt
                for src, tgt in edge_pairs
            ),
            "GetCustomer -> GetCustomerDB invocation missing",
        )

        # CalculatePrice -> ApplyPromotion
        self.assertTrue(
            any(
                "CalculatePrice" in src and "ApplyPromotion" in tgt
                for src, tgt in edge_pairs
            ),
            "CalculatePrice -> ApplyPromotion invocation missing",
        )

    # ── 3. Deterministic Impact Traversal ─────────────────────────

    def test_saveorderdb_is_changed(self):
        changed_ids = {a.asset_id for a in self.result.impact.changed}
        self.assertTrue(any("SaveOrderDB" in aid for aid in changed_ids))

    def test_saveorder_is_changed(self):
        changed_ids = {a.asset_id for a in self.result.impact.changed}
        self.assertTrue(any("SaveOrder" in aid and "SaveOrderDB" not in aid for aid in changed_ids))

    def test_orderprocessing_is_directly_affected(self):
        """OrderProcessing invokes SaveOrder, so it is directly affected at distance 1."""
        direct_map = {a.asset_id: a.distance for a in self.result.impact.directly_affected}
        matching = [aid for aid in direct_map if "services:OrderProcessing" in aid]
        self.assertEqual(len(matching), 1, f"OrderProcessing not directly affected: {direct_map}")
        self.assertEqual(direct_map[matching[0]], 1)

    def test_scheduler_is_transitively_affected(self):
        """scheduler invokes OrderProcessing, so it is transitively affected at distance 2."""
        trans_map = {a.asset_id: a.distance for a in self.result.impact.transitively_affected}
        matching = [aid for aid in trans_map if "scheduler" in aid]
        self.assertEqual(len(matching), 1, f"scheduler not transitively affected: {trans_map}")
        self.assertEqual(trans_map[matching[0]], 2)

    def test_unrelated_assets_excluded_from_impact(self):
        """Unrelated assets must NOT appear in the impact result."""
        all_impacted_ids = {a.asset_id for a in self.result.impact.all_impacted}
        for excluded in ["ValidateOrder", "GetCustomer", "CalculatePrice", "ApplyPromotion", "SendConfirmation"]:
            self.assertFalse(
                any(excluded in aid for aid in all_impacted_ids),
                f"{excluded} should not be affected by customerEmail change",
            )

    # ── 4. Deterministic Risk Scoring ─────────────────────────────

    def test_risk_score_is_positive_and_explained(self):
        risk = self.result.risk
        self.assertGreater(risk.score, 0)
        self.assertLessEqual(risk.score, 100)
        self.assertIn(risk.level, [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL])
        self.assertGreater(len(risk.drivers), 0)

        driver_texts = " ".join(d.description.lower() for d in risk.drivers)
        self.assertTrue("modified" in driver_texts)
        self.assertTrue("field" in driver_texts)
        self.assertTrue("mapping" in driver_texts)

    # ── 5. Regression Test Recommendations ────────────────────────

    def test_recommendations_cover_customer_email_persistence_path(self):
        recs = self.result.recommendations
        rec_names = [r.name for r in recs]
        rec_scenarios = [r.scenario for r in recs]
        combined = " ".join(rec_names + rec_scenarios)

        self.assertIn("customerEmail", combined)
        self.assertIn("SaveOrderDB", combined)
        self.assertIn("SaveOrder", combined)

    # ── 6. JSON Serialization & Roundtrip ─────────────────────────

    def test_serialization_structure(self):
        data = self.serialized
        self.assertIn("commits", data)
        self.assertIn("analysis", data)

        analysis = data["analysis"]
        for key in [
            "id", "title", "status", "baseCommit", "targetCommit",
            "summary", "affectedAssets", "risk", "dependencies",
            "regressionTests", "changes", "impact"
        ]:
            self.assertIn(key, analysis, f"Key '{key}' missing from serialized analysis")

    def test_json_roundtrip(self):
        parsed = json.loads(self.json_str)
        self.assertEqual(parsed["analysis"]["id"], self.serialized["analysis"]["id"])
        self.assertEqual(parsed["analysis"]["risk"]["score"], self.serialized["analysis"]["risk"]["score"])
        self.assertEqual(len(parsed["analysis"]["affectedAssets"]), len(self.serialized["analysis"]["affectedAssets"]))

    # ── 7. Same-Revision Zero-Change Verification ─────────────────

    def test_same_revision_produces_zero_changes(self):
        """Comparing a commit to itself must yield 0 changes and 0 risk."""
        same_result = analyze(
            repository_path=ROOT,
            package_path=PACKAGE_PATH,
            base_revision=BASE_REVISION,
            target_revision=BASE_REVISION,
        )
        same_data = serialize_analysis(same_result)
        analysis = same_data["analysis"]

        self.assertEqual(len(same_result.comparison.changes), 0)
        self.assertEqual(len(same_result.comparison.modified_assets), 0)
        self.assertEqual(len(same_result.impact.all_impacted), 0)
        self.assertEqual(same_result.risk.score, 0)
        self.assertEqual(same_result.risk.level, RiskLevel.LOW)
        self.assertEqual(len(same_result.recommendations), 0)

        self.assertEqual(len(analysis["affectedAssets"]), 0)
        self.assertEqual(analysis["risk"]["score"], 0)
        self.assertEqual(len(analysis["regressionTests"]), 0)
        self.assertEqual(len(analysis["changes"]), 0)


if __name__ == "__main__":
    unittest.main()
