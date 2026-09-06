import unittest
from pathlib import Path

from src.comparison import compare_revisions
from src.dependency import DependencyGraph, EdgeType, GraphNode, build_dependency_graph
from src.models import Asset, AssetSnapshot, AssetType, Change, ChangeType
from src.parser import parse_package


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "OrderProcessing"
BASE_REVISION = "02ccdc8"
TARGET_REVISION = "5d26f89"
PACKAGE_PATH = "demo/OrderProcessing"


class DependencyGraphBuildTests(unittest.TestCase):
    """Tests for graph construction from parsed demo package snapshots."""

    @classmethod
    def setUpClass(cls):
        cls.snapshots = parse_package(DEMO)
        cls.comparison = compare_revisions(ROOT, PACKAGE_PATH, BASE_REVISION, TARGET_REVISION)

    def test_builds_graph_from_parsed_snapshots(self):
        graph = build_dependency_graph(self.snapshots)
        self.assertGreater(len(graph.nodes), 0)
        self.assertGreater(len(graph.edges), 0)

    def test_contains_all_known_package_assets(self):
        graph = build_dependency_graph(self.snapshots)
        expected_ids = {s.asset.asset_id for s in self.snapshots}
        actual_ids = {nid for nid, n in graph.nodes.items() if not n.external}
        self.assertEqual(actual_ids, expected_ids)

    def test_save_order_invokes_save_order_db(self):
        graph = build_dependency_graph(self.snapshots)
        save_order = "OrderProcessing.orderProcessing.services:SaveOrder"
        save_order_db = "OrderProcessing.orderProcessing.adapters:SaveOrderDB"
        deps = graph.dependencies_of(save_order)
        invocation_targets = {
            e.target_id for e in deps if e.edge_type == EdgeType.INVOCATION
        }
        self.assertIn(save_order_db, invocation_targets)

    def test_get_customer_invokes_get_customer_db(self):
        graph = build_dependency_graph(self.snapshots)
        get_customer = "OrderProcessing.orderProcessing.services:GetCustomer"
        get_customer_db = "OrderProcessing.orderProcessing.adapters:GetCustomerDB"
        deps = graph.dependencies_of(get_customer)
        invocation_targets = {
            e.target_id for e in deps if e.edge_type == EdgeType.INVOCATION
        }
        self.assertIn(get_customer_db, invocation_targets)

    def test_calculate_price_invokes_apply_promotion(self):
        graph = build_dependency_graph(self.snapshots)
        calc = "OrderProcessing.orderProcessing.services:CalculatePrice"
        promo = "OrderProcessing.orderProcessing.services:ApplyPromotion"
        deps = graph.dependencies_of(calc)
        invocation_targets = {
            e.target_id for e in deps if e.edge_type == EdgeType.INVOCATION
        }
        self.assertIn(promo, invocation_targets)

    def test_scheduler_invokes_order_processing(self):
        graph = build_dependency_graph(self.snapshots)
        scheduler = "OrderProcessing.orderProcessing:scheduler"
        order_processing = "OrderProcessing.orderProcessing.services:OrderProcessing"
        deps = graph.dependencies_of(scheduler)
        invocation_targets = {
            e.target_id for e in deps if e.edge_type == EdgeType.INVOCATION
        }
        self.assertIn(order_processing, invocation_targets)

    def test_order_processing_invokes_five_services(self):
        graph = build_dependency_graph(self.snapshots)
        op = "OrderProcessing.orderProcessing.services:OrderProcessing"
        deps = graph.dependencies_of(op)
        invocation_targets = [
            e.target_id for e in deps if e.edge_type == EdgeType.INVOCATION
        ]
        self.assertEqual(len(invocation_targets), 5)

    def test_dependents_of_save_order_db_includes_save_order(self):
        graph = build_dependency_graph(self.snapshots)
        save_order_db = "OrderProcessing.orderProcessing.adapters:SaveOrderDB"
        dependents = graph.dependents_of(save_order_db)
        caller_ids = {e.source_id for e in dependents}
        self.assertIn("OrderProcessing.orderProcessing.services:SaveOrder", caller_ids)

    def test_external_references_become_external_nodes(self):
        graph = build_dependency_graph(self.snapshots)
        self.assertIn("pub.flow:getLastError", graph.nodes)
        self.assertTrue(graph.nodes["pub.flow:getLastError"].external)
        self.assertEqual(graph.nodes["pub.flow:getLastError"].asset_type, AssetType.UNKNOWN)

    def test_unknown_service_does_not_create_internal_node(self):
        graph = build_dependency_graph(self.snapshots)
        for nid, node in graph.nodes.items():
            if node.external:
                continue
            self.assertIn(nid, {s.asset.asset_id for s in self.snapshots})

    def test_changed_assets_are_marked(self):
        graph = build_dependency_graph(
            self.comparison.target_assets,
            changes=self.comparison.changes,
        )
        changed = graph.changed_node_ids()
        self.assertIn("OrderProcessing.orderProcessing.adapters:SaveOrderDB", changed)
        self.assertIn("OrderProcessing.orderProcessing.services:SaveOrder", changed)

    def test_unchanged_assets_are_not_marked_changed(self):
        graph = build_dependency_graph(
            self.comparison.target_assets,
            changes=self.comparison.changes,
        )
        scheduler = graph.nodes.get("OrderProcessing.orderProcessing:scheduler")
        self.assertIsNotNone(scheduler)
        self.assertFalse(scheduler.changed)

    def test_mapping_edges_connect_save_order_to_save_order_db(self):
        graph = build_dependency_graph(self.snapshots)
        save_order = "OrderProcessing.orderProcessing.services:SaveOrder"
        mapping_edges = [
            e for e in graph.dependencies_of(save_order)
            if e.edge_type == EdgeType.MAPPING
        ]
        mapping_targets = {e.target_id for e in mapping_edges}
        self.assertIn(
            "OrderProcessing.orderProcessing.adapters:SaveOrderDB",
            mapping_targets,
        )


if __name__ == "__main__":
    unittest.main()
