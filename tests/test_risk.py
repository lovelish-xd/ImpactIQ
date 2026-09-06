import unittest
from pathlib import Path

from src.comparison import compare_revisions, compare_snapshots
from src.dependency import build_dependency_graph
from src.impact import ImpactResult, ImpactType, ImpactedAsset, analyze_impact
from src.models import (
    Asset, AssetSnapshot, AssetType, Change, ChangeType, Field,
    Mapping, ServiceSignature,
)
from src.risk import RiskLevel, calculate_risk


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = "demo/OrderProcessing"
BASE_REVISION = "02ccdc8"
TARGET_REVISION = "5d26f89"


class RiskScoringTests(unittest.TestCase):
    """Tests for deterministic risk scoring."""

    @classmethod
    def setUpClass(cls):
        cls.comparison = compare_revisions(ROOT, PACKAGE_PATH, BASE_REVISION, TARGET_REVISION)
        cls.graph = build_dependency_graph(
            cls.comparison.target_assets,
            changes=cls.comparison.changes,
        )
        cls.impact = analyze_impact(cls.graph)
        cls.risk = calculate_risk(cls.comparison, cls.impact, cls.graph)

    def test_score_is_in_valid_range(self):
        self.assertGreaterEqual(self.risk.score, 0)
        self.assertLessEqual(self.risk.score, 100)

    def test_level_is_set(self):
        self.assertIn(self.risk.level, list(RiskLevel))

    def test_has_drivers(self):
        self.assertGreater(len(self.risk.drivers), 0)

    def test_drivers_have_positive_points(self):
        for driver in self.risk.drivers:
            self.assertGreater(driver.points, 0)

    def test_score_equals_sum_of_drivers(self):
        raw = sum(d.points for d in self.risk.drivers)
        expected = max(0, min(100, raw))
        self.assertEqual(self.risk.score, expected)

    def test_customer_email_change_has_nonzero_risk(self):
        self.assertGreater(self.risk.score, 0)

    def test_same_revision_has_zero_or_very_low_risk(self):
        no_change = compare_revisions(ROOT, PACKAGE_PATH, BASE_REVISION, BASE_REVISION)
        graph = build_dependency_graph(no_change.target_assets, changes=no_change.changes)
        impact = analyze_impact(graph)
        risk = calculate_risk(no_change, impact, graph)
        self.assertEqual(risk.score, 0)
        self.assertEqual(risk.level, RiskLevel.LOW)
        self.assertEqual(len(risk.drivers), 0)

    def test_signature_change_increases_risk(self):
        """A change with a field addition should score higher than no change."""
        asset = Asset(
            asset_id="test:A", name="A",
            asset_type=AssetType.ADAPTER_SERVICE,
            package_path="ns/A",
        )
        base = AssetSnapshot(
            asset=asset,
            signature=ServiceSignature(inputs=(Field(name="x", datatype="string"),)),
        )
        target = AssetSnapshot(
            asset=asset,
            signature=ServiceSignature(inputs=(
                Field(name="x", datatype="string"),
                Field(name="y", datatype="string"),
            )),
        )
        comp = compare_snapshots([base], [target])
        graph = build_dependency_graph(comp.target_assets, changes=comp.changes)
        impact = analyze_impact(graph)
        risk = calculate_risk(comp, impact, graph)
        self.assertGreater(risk.score, 0)

    def test_multiple_dependents_increase_risk(self):
        """More downstream dependents should produce a higher score."""
        asset_b = Asset(
            asset_id="test:B", name="B",
            asset_type=AssetType.ADAPTER_SERVICE,
            package_path="ns/B",
        )
        base_b = AssetSnapshot(
            asset=asset_b,
            signature=ServiceSignature(inputs=(Field(name="x", datatype="string"),)),
        )
        target_b = AssetSnapshot(
            asset=asset_b,
            signature=ServiceSignature(inputs=(
                Field(name="x", datatype="string"),
                Field(name="y", datatype="string"),
            )),
        )
        comp_single = compare_snapshots([base_b], [target_b])
        graph_single = build_dependency_graph(comp_single.target_assets, changes=comp_single.changes)
        impact_single = analyze_impact(graph_single)
        risk_single = calculate_risk(comp_single, impact_single, graph_single)

        # Now add 2 directly affected assets via synthetic impact
        impact_multi = ImpactResult(
            changed=impact_single.changed,
            directly_affected=(
                ImpactedAsset(
                    asset_id="test:C", impact_type=ImpactType.DIRECTLY_AFFECTED,
                    distance=1, reason="Invokes B",
                ),
                ImpactedAsset(
                    asset_id="test:D", impact_type=ImpactType.DIRECTLY_AFFECTED,
                    distance=1, reason="Invokes B",
                ),
            ),
            transitively_affected=(),
        )
        risk_multi = calculate_risk(comp_single, impact_multi, graph_single)
        self.assertGreater(risk_multi.score, risk_single.score)


if __name__ == "__main__":
    unittest.main()
