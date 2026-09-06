import unittest

from src.comparison import compare_revisions, compare_snapshots
from src.models import Asset, AssetSnapshot, AssetType, ChangeType, Field, Mapping, ServiceSignature

from test_parser import DEMO, ROOT


BASE_REVISION = "02ccdc8"
TARGET_REVISION = "5d26f89"
PACKAGE_PATH = "demo/OrderProcessing"


class GitComparisonTests(unittest.TestCase):
    def test_compares_customer_email_persistence_commit(self):
        result = compare_revisions(ROOT, PACKAGE_PATH, BASE_REVISION, TARGET_REVISION)

        self.assertEqual(result.base_revision, BASE_REVISION)
        self.assertEqual(result.target_revision, TARGET_REVISION)
        self.assertEqual(len(result.added_assets), 0)
        self.assertEqual(len(result.removed_assets), 0)

        modified_ids = {snapshot.asset.asset_id for snapshot in result.modified_assets}
        self.assertEqual(
            modified_ids,
            {
                "OrderProcessing.orderProcessing.adapters:SaveOrderDB",
                "OrderProcessing.orderProcessing.services:SaveOrder",
            },
        )

        field_additions = [
            change
            for change in result.changes
            if change.change_type == ChangeType.FIELD_ADDED
        ]
        self.assertTrue(
            any(
                change.affected_asset.asset_id == "OrderProcessing.orderProcessing.adapters:SaveOrderDB"
                and change.metadata["scope"] == "signature.inputs"
                and change.after.name == "customerEmail"
                for change in field_additions
            )
        )

        mapping_additions = [
            change
            for change in result.changes
            if change.change_type == ChangeType.MAPPING_ADDED
        ]
        self.assertTrue(
            any(
                change.affected_asset.asset_id == "OrderProcessing.orderProcessing.services:SaveOrder"
                and change.after.source_path == "/OrderDocument/order/customerEmail;1;0"
                and change.after.target_path == "/SaveOrderDBInput/customerEmail;1;0"
                for change in mapping_additions
            )
        )

        sql_changes = [
            change
            for change in result.changes
            if change.metadata.get("component") == "sql"
        ]
        self.assertEqual(len(sql_changes), 1)
        self.assertEqual(sql_changes[0].description, "SQL modified: query.sql")
        self.assertNotIn("customer_email", sql_changes[0].before)
        self.assertIn("customer_email", sql_changes[0].after)

    def test_same_revision_has_no_changes(self):
        result = compare_revisions(ROOT, PACKAGE_PATH, BASE_REVISION, BASE_REVISION)

        self.assertEqual(result.changes, ())
        self.assertEqual(result.added_assets, ())
        self.assertEqual(result.removed_assets, ())
        self.assertEqual(result.modified_assets, ())
        self.assertGreater(len(result.unchanged_assets), 0)

    def test_detects_asset_addition_and_removal_from_snapshots(self):
        base = AssetSnapshot(
            asset=Asset(
                asset_id="OrderProcessing.orderProcessing.services:OldService",
                name="OldService",
                asset_type=AssetType.FLOW_SERVICE,
                package_path="ns/orderProcessing/services/OldService",
            )
        )
        target = AssetSnapshot(
            asset=Asset(
                asset_id="OrderProcessing.orderProcessing.services:NewService",
                name="NewService",
                asset_type=AssetType.FLOW_SERVICE,
                package_path="ns/orderProcessing/services/NewService",
            )
        )

        result = compare_snapshots([base], [target])

        self.assertEqual(result.added_assets, (target,))
        self.assertEqual(result.removed_assets, (base,))
        self.assertEqual(
            [change.change_type for change in result.changes],
            [ChangeType.ADDED, ChangeType.REMOVED],
        )

    def test_detects_field_addition_and_removal_from_snapshots(self):
        asset = Asset(
            asset_id="OrderProcessing.orderProcessing.adapters:SaveOrderDB",
            name="SaveOrderDB",
            asset_type=AssetType.ADAPTER_SERVICE,
            package_path="ns/orderProcessing/adapters/SaveOrderDB",
        )
        base = AssetSnapshot(
            asset=asset,
            signature=ServiceSignature(inputs=(Field(name="orderId", datatype="string"),)),
        )
        target = AssetSnapshot(
            asset=asset,
            signature=ServiceSignature(inputs=(Field(name="customerEmail", datatype="string"),)),
        )

        result = compare_snapshots([base], [target])
        change_types = [change.change_type for change in result.changes]

        self.assertIn(ChangeType.FIELD_ADDED, change_types)
        self.assertIn(ChangeType.FIELD_REMOVED, change_types)

    def test_detects_mapping_change_from_snapshots(self):
        asset = Asset(
            asset_id="OrderProcessing.orderProcessing.services:SaveOrder",
            name="SaveOrder",
            asset_type=AssetType.FLOW_SERVICE,
            package_path="ns/orderProcessing/services/SaveOrder",
        )
        base = AssetSnapshot(
            asset=asset,
            mappings=(
                Mapping(
                    source_path="/OrderDocument/order/status;1;0",
                    target_path="/SaveOrderDBInput/orderStatus;1;0",
                    metadata={"order": "0"},
                ),
            ),
        )
        target = AssetSnapshot(
            asset=asset,
            mappings=(
                Mapping(
                    source_path="/OrderDocument/order/status;1;0",
                    target_path="/SaveOrderDBInput/status;1;0",
                    metadata={"order": "0"},
                ),
            ),
        )

        result = compare_snapshots([base], [target])
        mapping_changes = [
            change
            for change in result.changes
            if change.metadata.get("component") == "mapping"
        ]

        self.assertEqual(len(mapping_changes), 1)
        self.assertEqual(mapping_changes[0].change_type, ChangeType.MODIFIED)
        self.assertEqual(mapping_changes[0].after.target_path, "/SaveOrderDBInput/status;1;0")


if __name__ == "__main__":
    unittest.main()
