"""Discovery and parsing for the webMethods-shaped demo artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

from src.models import (
    Asset,
    AssetSnapshot,
    AssetType,
    Field,
    Invocation,
    Mapping,
    ServiceSignature,
)


class ParserError(Exception):
    """Raised when a repository artifact cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class DiscoveredAsset:
    """Filesystem location for one discovered webMethods asset."""

    asset: Asset
    asset_dir: Path
    node_path: Path
    flow_path: Path | None = None
    query_path: Path | None = None


def discover_assets(package_dir: str | Path) -> tuple[DiscoveredAsset, ...]:
    """Discover supported assets under a single webMethods package directory."""

    package_root = Path(package_dir)
    if not package_root.exists():
        raise ParserError(f"Package directory does not exist: {package_root}")
    if not package_root.is_dir():
        raise ParserError(f"Package path is not a directory: {package_root}")

    discovered: list[DiscoveredAsset] = []
    for node_path in sorted(package_root.rglob("node.ndf")):
        root = _parse_xml(node_path)
        asset_type = _asset_type_for_node(node_path, root)
        if asset_type is None:
            continue

        asset_dir = node_path.parent
        asset_id = _asset_id(package_root, asset_dir, asset_type)
        metadata = _asset_metadata(root, asset_type)
        asset = Asset(
            asset_id=asset_id,
            name=asset_id.split(":", 1)[-1],
            asset_type=asset_type,
            package_path=_relative_posix(package_root, asset_dir),
            metadata=metadata,
        )
        flow_path = asset_dir / "flow.xml"
        query_path = asset_dir / "query.sql"
        discovered.append(
            DiscoveredAsset(
                asset=asset,
                asset_dir=asset_dir,
                node_path=node_path,
                flow_path=flow_path if flow_path.exists() else None,
                query_path=query_path if query_path.exists() else None,
            )
        )

    return tuple(discovered)


def parse_package(package_dir: str | Path) -> tuple[AssetSnapshot, ...]:
    """Discover and parse all supported assets in a package directory."""

    return tuple(parse_discovered_asset(asset) for asset in discover_assets(package_dir))


def parse_discovered_asset(discovered: DiscoveredAsset) -> AssetSnapshot:
    """Parse a discovered asset with the correct asset-specific parser."""

    if discovered.asset.asset_type == AssetType.FLOW_SERVICE:
        return parse_flow_service(discovered)
    if discovered.asset.asset_type == AssetType.DOCUMENT_TYPE:
        return parse_document_type(discovered)
    if discovered.asset.asset_type == AssetType.ADAPTER_SERVICE:
        return parse_adapter_service(discovered)
    raise ParserError(f"Unsupported asset type: {discovered.asset.asset_type}")


def parse_flow_service(discovered: DiscoveredAsset) -> AssetSnapshot:
    """Parse a Flow Service node.ndf and flow.xml into an AssetSnapshot."""

    if discovered.flow_path is None:
        raise ParserError(f"Flow Service is missing flow.xml: {discovered.asset.package_path}")

    node_root = _parse_xml(discovered.node_path)
    flow_root = _parse_xml(discovered.flow_path)
    if flow_root.tag != "FLOW":
        raise ParserError(f"Expected FLOW root in {discovered.flow_path}, found {flow_root.tag}")

    signature = _parse_service_signature(node_root)
    facts = {
        "flow_version": flow_root.attrib.get("VERSION", ""),
        "cleanup": flow_root.attrib.get("CLEANUP", ""),
        **_direct_values(node_root),
    }

    return AssetSnapshot(
        asset=discovered.asset,
        signature=signature,
        mappings=_parse_mappings(flow_root),
        invocations=_parse_invocations(flow_root, discovered.asset.asset_id),
        facts=facts,
    )


def parse_document_type(discovered: DiscoveredAsset) -> AssetSnapshot:
    """Parse a Document Type node.ndf into an AssetSnapshot."""

    root = _parse_xml(discovered.node_path)
    record = root.find("./record[@name='record']")
    if record is None:
        raise ParserError(f"Document Type is missing record metadata: {discovered.node_path}")

    return AssetSnapshot(
        asset=discovered.asset,
        fields=_parse_field_children(record),
        facts=_direct_values(record),
    )


def parse_adapter_service(discovered: DiscoveredAsset) -> AssetSnapshot:
    """Parse an Adapter Service node.ndf and optional query.sql sidecar."""

    root = _parse_xml(discovered.node_path)
    values = _direct_values(root)
    if values.get("svc_type") != "AdapterService":
        raise ParserError(f"Expected AdapterService in {discovered.node_path}")

    facts = dict(values)
    if discovered.query_path is not None:
        facts["query_sql"] = discovered.query_path.read_text(encoding="utf-8")
        facts["query_path"] = discovered.query_path.name

    return AssetSnapshot(
        asset=discovered.asset,
        signature=_parse_service_signature(root),
        facts=facts,
    )


def _parse_xml(path: Path) -> ET.Element:
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ParserError(f"Malformed XML in {path}: {exc}") from exc
    except OSError as exc:
        raise ParserError(f"Unable to read {path}: {exc}") from exc


def _asset_type_for_node(node_path: Path, root: ET.Element) -> AssetType | None:
    values = _direct_values(root)
    svc_type = values.get("svc_type")
    if svc_type == "flow" and (node_path.parent / "flow.xml").exists():
        return AssetType.FLOW_SERVICE
    if svc_type == "AdapterService":
        return AssetType.ADAPTER_SERVICE
    if root.find("./record[@name='record']") is not None and "docs" in node_path.parts:
        return AssetType.DOCUMENT_TYPE
    return None


def _asset_metadata(root: ET.Element, asset_type: AssetType) -> dict[str, str]:
    if asset_type == AssetType.DOCUMENT_TYPE:
        record = root.find("./record[@name='record']")
        return _direct_values(record) if record is not None else {}
    return _direct_values(root)


def _asset_id(package_root: Path, asset_dir: Path, asset_type: AssetType) -> str:
    package_name = package_root.name
    relative = asset_dir.relative_to(package_root).parts
    if len(relative) < 2 or relative[0] != "ns":
        raise ParserError(f"Cannot derive webMethods asset id from {asset_dir}")

    namespace_parts = list(relative[1:])
    if asset_type in {AssetType.FLOW_SERVICE, AssetType.ADAPTER_SERVICE, AssetType.DOCUMENT_TYPE}:
        asset_name = namespace_parts[-1]
        namespace = ".".join([package_name, *namespace_parts[:-1]])
        return f"{namespace}:{asset_name}"

    raise ParserError(f"Cannot derive asset id for {asset_type}: {asset_dir}")


def _relative_posix(package_root: Path, path: Path) -> str:
    return path.relative_to(package_root).as_posix()


def _direct_values(element: ET.Element | None) -> dict[str, str]:
    if element is None:
        return {}
    return {
        value.attrib["name"]: (value.text or "").strip()
        for value in element.findall("./value[@name]")
    }


def _parse_service_signature(root: ET.Element) -> ServiceSignature:
    signature = root.find("./record[@name='svc_sig']")
    if signature is None:
        return ServiceSignature()
    sig_in = signature.find("./record[@name='sig_in']")
    sig_out = signature.find("./record[@name='sig_out']")
    return ServiceSignature(
        inputs=_parse_field_children(sig_in),
        outputs=_parse_field_children(sig_out),
    )


def _parse_field_children(record: ET.Element | None, parent_path: str | None = None) -> tuple[Field, ...]:
    if record is None:
        return ()

    fields: list[Field] = []
    rec_fields = record.find("./array[@name='rec_fields']")
    if rec_fields is None:
        return ()

    for child in rec_fields.findall("./record"):
        values = _direct_values(child)
        name = values.get("field_name")
        if not name:
            continue
        datatype = values.get("field_type", "unknown")
        children = _parse_field_children(child, _join_path(parent_path, name))
        fields.append(
            Field(
                name=name,
                datatype=datatype,
                required=_required_flag(values),
                parent_path=parent_path,
                reference=values.get("rec_ref"),
                dimension=_integer_or_none(values.get("field_dim")),
                children=children,
                metadata={
                    key: value
                    for key, value in values.items()
                    if key not in {"field_name", "field_type", "rec_ref", "field_dim"}
                },
            )
        )

    return tuple(fields)


def _required_flag(values: dict[str, str]) -> bool | None:
    field_opt = values.get("field_opt")
    if field_opt is None:
        return None
    return field_opt.lower() != "true"


def _integer_or_none(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _join_path(parent_path: str | None, name: str) -> str:
    return name if parent_path is None else f"{parent_path}/{name}"


def _parse_invocations(flow_root: ET.Element, source_service: str) -> tuple[Invocation, ...]:
    invocations: list[Invocation] = []
    for index, invoke in enumerate(flow_root.findall(".//INVOKE")):
        target = invoke.attrib.get("SERVICE")
        if not target:
            continue
        metadata = {
            "order": str(index),
            **{
                key.lower().replace("-", "_"): value
                for key, value in invoke.attrib.items()
                if key != "SERVICE"
            },
        }
        invocations.append(
            Invocation(
                source_service=source_service,
                target_service=target,
                reference_type="INVOKE",
                metadata=metadata,
            )
        )
    return tuple(invocations)


def _parse_mappings(flow_root: ET.Element) -> tuple[Mapping, ...]:
    mappings: list[Mapping] = []

    def visit(element: ET.Element, mode: str | None = None) -> None:
        current_mode = element.attrib.get("MODE", mode) if element.tag == "MAP" else mode
        if element.tag == "MAPCOPY":
            source = element.attrib.get("FROM")
            target = element.attrib.get("TO")
            if source and target:
                mappings.append(
                    Mapping(
                        source_path=source,
                        target_path=target,
                        mapping_type="MAPCOPY",
                        metadata={
                            "order": str(len(mappings)),
                            **({"mode": current_mode} if current_mode else {}),
                        },
                    )
                )
        for child in element:
            visit(child, current_mode)

    visit(flow_root)
    return tuple(mappings)
