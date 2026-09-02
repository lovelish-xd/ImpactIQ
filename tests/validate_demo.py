"""Validate the canonical demo's webMethods-shaped artifacts.

This is fixture validation only. It is deliberately not the ImpactIQ parser or
comparison engine.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo" / "OrderProcessing"
NAMESPACE = "OrderProcessing.orderProcessing"


def parse_xml(path: Path) -> ET.Element:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise AssertionError(f"XML is not well-formed: {path}: {exc}") from exc


def value_map(root: ET.Element) -> dict[str, str]:
    return {
        element.attrib["name"]: (element.text or "").strip()
        for element in root.findall(".//value[@name]")
    }


def asset_name(path: Path) -> str:
    relative = path.relative_to(DEMO).parts
    if relative[-2] == "scheduler":
        return f"{NAMESPACE}:scheduler"
    if "services" in relative:
        folder = relative[relative.index("services") + 1]
        return f"{NAMESPACE}.services:{folder}"
    if "scheduler" in relative:
        folder = relative[relative.index("scheduler") + 1]
        return f"{NAMESPACE}.scheduler:{folder}"
    if "adapters" in relative:
        folder = relative[relative.index("adapters") + 1]
        return f"{NAMESPACE}.adapters:{folder}"
    if "docs" in relative:
        folder = relative[relative.index("docs") + 1]
        return f"{NAMESPACE}.docs:{folder}"
    raise AssertionError(f"Cannot determine asset name from {path}")


def collect_assets() -> set[str]:
    assets: set[str] = set()
    for path in DEMO.rglob("node.ndf"):
        root = parse_xml(path)
        values = value_map(root)
        if path.parts[-3] == "services" or path.parts[-2] == "scheduler":
            assert values.get("svc_type") == "flow", path
        elif path.parts[-3] == "adapters":
            assert values.get("svc_type") == "AdapterService", path
        elif path.parts[-3] == "docs":
            assert root.find("record") is not None, path
        assets.add(asset_name(path))
    return assets


def validate_flows(assets: set[str]) -> None:
    service_references: set[str] = set()
    for path in DEMO.rglob("flow.xml"):
        root = parse_xml(path)
        assert root.tag == "FLOW", path
        assert root.attrib.get("VERSION") == "3.0", path
        for invoke in root.findall(".//INVOKE"):
            service = invoke.attrib.get("SERVICE")
            assert service, path
            service_references.add(service)

        for map_copy in root.findall(".//MAPCOPY"):
            assert map_copy.attrib.get("FROM"), path
            assert map_copy.attrib.get("TO"), path

    local_references = {
        reference
        for reference in service_references
        if reference.startswith(f"{NAMESPACE}.")
    }
    assert local_references <= assets, sorted(local_references - assets)
    assert f"{NAMESPACE}.services:ApplyPromotion" in local_references
    assert f"{NAMESPACE}.services:OrderProcessing" in local_references
    assert f"{NAMESPACE}.adapters:GetCustomerDB" in local_references
    assert f"{NAMESPACE}.adapters:SaveOrderDB" in local_references


def validate_scheduler() -> None:
    scheduler = DEMO / "ns" / "orderProcessing" / "scheduler"
    root = parse_xml(scheduler / "flow.xml")
    values = value_map(parse_xml(scheduler / "node.ndf"))
    comments = [comment.text.strip() for comment in root.findall(".//COMMENT") if comment.text]
    invoked_services = {invoke.attrib["SERVICE"] for invoke in root.findall(".//INVOKE")}

    assert values["svc_type"] == "flow"
    assert values["node_type"] == "service"
    assert "--try block--" in comments
    assert "--catch block--" in comments
    assert "pub.flow:getLastError" in invoked_services
    assert f"{NAMESPACE}.services:OrderProcessing" in invoked_services


def validate_documents() -> None:
    order = parse_xml(DEMO / "ns" / "orderProcessing" / "docs" / "OrderDocument" / "node.ndf")
    customer = parse_xml(DEMO / "ns" / "orderProcessing" / "docs" / "CustomerDocument" / "node.ndf")
    order_fields = {field.text.strip() for field in order.findall('.//value[@name="field_name"]') if field.text}
    customer_fields = {field.text.strip() for field in customer.findall('.//value[@name="field_name"]') if field.text}
    assert {"promotionCode", "discountAmount"} <= order_fields
    assert "loyaltyTier" in customer_fields


def validate_adapters() -> None:
    for name in ("GetCustomerDB", "SaveOrderDB"):
        adapter = DEMO / "ns" / "orderProcessing" / "adapters" / name
        root = parse_xml(adapter / "node.ndf")
        values = value_map(root)
        assert values["svc_type"] == "AdapterService"
        assert values["IRTNODE_VERSION"] == "1"
        query = (adapter / "query.sql").read_text(encoding="utf-8")
        assert re.search(r"\bSELECT\b|\bINSERT\b", query, re.IGNORECASE)

    get_query = (DEMO / "ns" / "orderProcessing" / "adapters" / "GetCustomerDB" / "query.sql").read_text(encoding="utf-8")
    assert "loyalty_tier" in get_query
    assert "ACTIVE" in get_query


def validate_git_migration() -> None:
    assert not (ROOT / "demo" / "v1").exists()
    assert not (ROOT / "demo" / "v2").exists()
    for ref in ("demo-original", "demo-standardized", "demo-scheduler-entrypoint", "demo-direct-scheduler"):
        result = subprocess.run(
            ["git", "-c", f"safe.directory={ROOT}", "rev-parse", "--verify", ref],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Missing Git ref {ref}: {result.stderr.strip()}"


def main() -> int:
    assert DEMO.exists(), f"Missing canonical demo: {DEMO}"
    assets = collect_assets()
    assert len(assets) == 12, sorted(assets)
    validate_flows(assets)
    validate_scheduler()
    validate_documents()
    validate_adapters()
    validate_git_migration()
    print("ImpactIQ canonical demo validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
