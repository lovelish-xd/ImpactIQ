from pathlib import Path
import tempfile
import unittest

from src.models import AssetType
from src.parser import ParserError, discover_assets, parse_package


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "OrderProcessing"


def snapshot_by_id():
    return {snapshot.asset.asset_id: snapshot for snapshot in parse_package(DEMO)}


class WebMethodsParserTests(unittest.TestCase):
    def test_discovers_supported_demo_assets(self):
        discovered = discover_assets(DEMO)
        asset_ids = {item.asset.asset_id for item in discovered}

        self.assertIn("OrderProcessing.orderProcessing.services:OrderProcessing", asset_ids)
        self.assertIn("OrderProcessing.orderProcessing.docs:OrderDocument", asset_ids)
        self.assertIn("OrderProcessing.orderProcessing.adapters:SaveOrderDB", asset_ids)
        self.assertIn("OrderProcessing.orderProcessing:scheduler", asset_ids)

        asset_types = {item.asset.asset_id: item.asset.asset_type for item in discovered}
        self.assertEqual(
            asset_types["OrderProcessing.orderProcessing.services:OrderProcessing"],
            AssetType.FLOW_SERVICE,
        )
        self.assertEqual(
            asset_types["OrderProcessing.orderProcessing.docs:OrderDocument"],
            AssetType.DOCUMENT_TYPE,
        )
        self.assertEqual(
            asset_types["OrderProcessing.orderProcessing.adapters:SaveOrderDB"],
            AssetType.ADAPTER_SERVICE,
        )

    def test_parses_order_processing_flow_invocations_and_mapcopy(self):
        snapshots = snapshot_by_id()
        snapshot = snapshots["OrderProcessing.orderProcessing.services:OrderProcessing"]

        targets = [invocation.target_service for invocation in snapshot.invocations]
        self.assertEqual(
            targets,
            [
                "OrderProcessing.orderProcessing.services:ValidateOrder",
                "OrderProcessing.orderProcessing.services:GetCustomer",
                "OrderProcessing.orderProcessing.services:CalculatePrice",
                "OrderProcessing.orderProcessing.services:SaveOrder",
                "OrderProcessing.orderProcessing.services:SendConfirmation",
            ],
        )
        self.assertEqual(snapshot.facts["flow_version"], "3.0")
        self.assertEqual(len(snapshot.mappings), 1)
        self.assertEqual(snapshot.mappings[0].source_path, "/OrderProcessingInput;3;0")
        self.assertEqual(snapshot.mappings[0].target_path, "/OrderDocument;3;0")
        self.assertEqual(snapshot.mappings[0].metadata["mode"], "STANDALONE")

    def test_parses_order_document_fields(self):
        snapshots = snapshot_by_id()
        snapshot = snapshots["OrderProcessing.orderProcessing.docs:OrderDocument"]
        order = next(field for field in snapshot.fields if field.name == "order")
        child_names = {field.name for field in order.children}

        self.assertEqual(order.datatype, "record")
        self.assertIn("customerEmail", child_names)
        self.assertIn("totalAmount", child_names)
        customer_email = next(field for field in order.children if field.name == "customerEmail")
        self.assertEqual(customer_email.datatype, "string")
        self.assertEqual(customer_email.parent_path, "order")
        self.assertIsNone(customer_email.required)
        self.assertEqual(customer_email.metadata["nillable"], "true")

    def test_parses_save_order_db_signature_and_query(self):
        snapshots = snapshot_by_id()
        snapshot = snapshots["OrderProcessing.orderProcessing.adapters:SaveOrderDB"]
        input_names = [field.name for field in snapshot.signature.inputs]
        output_names = [field.name for field in snapshot.signature.outputs]

        self.assertEqual(snapshot.asset.asset_type, AssetType.ADAPTER_SERVICE)
        self.assertIn("customerEmail", input_names)
        self.assertIn("$connectionName", input_names)
        self.assertEqual(output_names, ["rowsAffected"])
        self.assertEqual(snapshot.facts["IRTNODE_VERSION"], "1")
        self.assertIn("customer_email", snapshot.facts["query_sql"])
        self.assertEqual(snapshot.facts["query_path"], "query.sql")

    def test_parses_save_order_customer_email_mapping(self):
        snapshots = snapshot_by_id()
        snapshot = snapshots["OrderProcessing.orderProcessing.services:SaveOrder"]
        mappings = {(mapping.source_path, mapping.target_path) for mapping in snapshot.mappings}

        self.assertIn(
            (
                "/OrderDocument/order/customerEmail;1;0",
                "/SaveOrderDBInput/customerEmail;1;0",
            ),
            mappings,
        )

    def test_malformed_xml_raises_parser_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Path(temp_dir) / "BrokenPackage"
            service = package / "ns" / "broken" / "services" / "BrokenFlow"
            service.mkdir(parents=True)
            (service / "node.ndf").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<Values version="2.0"><value name="svc_type">flow</value></Values>
""",
                encoding="utf-8",
            )
            (service / "flow.xml").write_text("<FLOW><SEQUENCE></FLOW>", encoding="utf-8")

            discovered = discover_assets(package)
            self.assertEqual(len(discovered), 1)
            with self.assertRaisesRegex(ParserError, "Malformed XML"):
                parse_package(package)


if __name__ == "__main__":
    unittest.main()
