import unittest

from src.models import (
    Asset,
    AssetSnapshot,
    AssetType,
    Change,
    ChangeType,
    Field,
    Invocation,
    Mapping,
    ServiceSignature,
)


class DomainModelTests(unittest.TestCase):
    def test_construct_asset(self):
        asset = Asset(
            asset_id="OrderProcessing.orderProcessing.adapters:SaveOrderDB",
            name="SaveOrderDB",
            asset_type=AssetType.ADAPTER_SERVICE,
            package_path="demo/OrderProcessing/ns/orderProcessing/adapters/SaveOrderDB",
            metadata={"svc_type": "AdapterService"},
        )

        self.assertEqual(asset.name, "SaveOrderDB")
        self.assertEqual(asset.asset_type, AssetType.ADAPTER_SERVICE)
        self.assertEqual(asset.metadata["svc_type"], "AdapterService")

    def test_construct_service_signature_with_fields(self):
        order_document = Field(
            name="OrderDocument",
            datatype="recref",
            reference="OrderProcessing.orderProcessing.docs:OrderDocument",
        )
        rows_affected = Field(name="rowsAffected", datatype="string")
        signature = ServiceSignature(inputs=(order_document,), outputs=(rows_affected,))

        self.assertEqual(signature.inputs[0].name, "OrderDocument")
        self.assertEqual(signature.inputs[0].reference, "OrderProcessing.orderProcessing.docs:OrderDocument")
        self.assertEqual(signature.outputs[0].datatype, "string")

    def test_construct_mapping(self):
        mapping = Mapping(
            source_path="/OrderDocument/order/customerEmail;1;0",
            target_path="/SaveOrderDBInput/customerEmail;1;0",
        )

        self.assertEqual(mapping.mapping_type, "MAPCOPY")
        self.assertIn("customerEmail", mapping.source_path)
        self.assertIn("SaveOrderDBInput", mapping.target_path)

    def test_construct_invocation(self):
        invocation = Invocation(
            source_service="OrderProcessing.orderProcessing.services:SaveOrder",
            target_service="OrderProcessing.orderProcessing.adapters:SaveOrderDB",
        )

        self.assertEqual(invocation.reference_type, "INVOKE")
        self.assertTrue(invocation.target_service.endswith(":SaveOrderDB"))

    def test_construct_asset_snapshot(self):
        asset = Asset(
            asset_id="OrderProcessing.orderProcessing.services:SaveOrder",
            name="SaveOrder",
            asset_type=AssetType.FLOW_SERVICE,
            package_path="demo/OrderProcessing/ns/orderProcessing/services/SaveOrder",
        )
        mapping = Mapping(
            source_path="/OrderDocument/order/customerEmail;1;0",
            target_path="/SaveOrderDBInput/customerEmail;1;0",
        )
        invocation = Invocation(
            source_service=asset.asset_id,
            target_service="OrderProcessing.orderProcessing.adapters:SaveOrderDB",
        )
        snapshot = AssetSnapshot(
            asset=asset,
            mappings=[mapping],
            invocations=[invocation],
            facts={"flow_version": "3.0"},
        )

        self.assertEqual(snapshot.asset.name, "SaveOrder")
        self.assertEqual(snapshot.mappings[0], mapping)
        self.assertEqual(snapshot.invocations[0], invocation)
        self.assertEqual(snapshot.facts["flow_version"], "3.0")

    def test_construct_change(self):
        asset = Asset(
            asset_id="OrderProcessing.orderProcessing.adapters:SaveOrderDB",
            name="SaveOrderDB",
            asset_type=AssetType.ADAPTER_SERVICE,
            package_path="demo/OrderProcessing/ns/orderProcessing/adapters/SaveOrderDB",
        )
        change = Change(
            change_type=ChangeType.FIELD_ADDED,
            affected_asset=asset,
            before=None,
            after=Field(name="customerEmail", datatype="string"),
            description="SaveOrderDBInput adds customerEmail.",
        )

        self.assertEqual(change.change_type, ChangeType.FIELD_ADDED)
        self.assertEqual(change.after.name, "customerEmail")
        self.assertIn("customerEmail", change.description)


if __name__ == "__main__":
    unittest.main()
