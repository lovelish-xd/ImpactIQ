"""JSON serialization for ImpactIQ analysis results.

Produces a JSON structure compatible with the existing UI contract
(see ui/mock-analysis.json) while faithfully representing the
deterministic analysis data.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from src.analyzer import AnalysisResult
from src.dependency import DependencyGraph, EdgeType
from src.impact import ImpactResult, ImpactType
from src.models import AssetType, ChangeType


def serialize_analysis(result: AnalysisResult) -> dict[str, Any]:
    """Convert an AnalysisResult into a JSON-serializable dictionary.

    The output shape is compatible with the existing UI mock contract.
    """

    return {
        "commits": _serialize_commits(result),
        "analysis": {
            "id": f"analysis-{result.base_revision}-{result.target_revision}",
            "title": _derive_title(result),
            "status": "Analysis complete",
            "baseCommit": result.base_revision,
            "targetCommit": result.target_revision,
            "summary": _serialize_summary(result),
            "affectedAssets": _serialize_affected_assets(result),
            "risk": _serialize_risk(result),
            "dependencies": _serialize_dependencies(result),
            "regressionTests": _serialize_tests(result),
            "changes": _serialize_changes(result),
            "impact": _serialize_impact(result),
        },
    }


def serialize_analysis_json(result: AnalysisResult, indent: int = 2) -> str:
    """Serialize an AnalysisResult to a JSON string."""
    return json.dumps(serialize_analysis(result), indent=indent, default=_json_default)


def _serialize_commits(result: AnalysisResult) -> dict[str, Any]:
    return {
        "base": [
            {
                "id": result.base_revision,
                "label": f"{result.base_revision[:7]} - Base revision",
                "description": f"Base revision for comparison",
            }
        ],
        "target": [
            {
                "id": result.target_revision,
                "label": f"{result.target_revision[:7]} - Target revision",
                "description": f"Target revision for comparison",
            }
        ],
    }


def _derive_title(result: AnalysisResult) -> str:
    """Derive a title from the detected changes."""
    n_changes = len(result.comparison.changes)
    n_modified = len(result.comparison.modified_assets)
    n_added = len(result.comparison.added_assets)
    n_removed = len(result.comparison.removed_assets)

    if n_changes == 0:
        return "No changes detected"

    parts = []
    if n_modified:
        parts.append(f"{n_modified} modified")
    if n_added:
        parts.append(f"{n_added} added")
    if n_removed:
        parts.append(f"{n_removed} removed")

    return f"Impact analysis: {', '.join(parts)} asset(s)"


def _serialize_summary(result: AnalysisResult) -> dict[str, Any]:
    """Generate summary from actual change data."""

    items: list[str] = []
    for change in result.comparison.changes:
        if change.change_type in (ChangeType.ADDED, ChangeType.REMOVED, ChangeType.MODIFIED):
            if change.metadata.get("component") == "sql":
                items.append(change.description)
            elif change.change_type != ChangeType.MODIFIED:
                items.append(change.description)
        elif change.change_type in (
            ChangeType.FIELD_ADDED, ChangeType.FIELD_REMOVED, ChangeType.FIELD_MODIFIED,
            ChangeType.MAPPING_ADDED, ChangeType.MAPPING_REMOVED,
            ChangeType.INVOCATION_ADDED, ChangeType.INVOCATION_REMOVED,
            ChangeType.SIGNATURE_CHANGED,
        ):
            items.append(change.description)

    headline = _derive_title(result)
    if result.impact.directly_affected:
        names = [
            result.graph.nodes[a.asset_id].asset_name
            for a in result.impact.directly_affected
            if a.asset_id in result.graph.nodes
        ]
        if names:
            headline += f". Directly affects {', '.join(names)}"

    return {
        "headline": headline,
        "items": items,
    }


def _serialize_affected_assets(result: AnalysisResult) -> list[dict[str, Any]]:
    """Serialize all changed and impacted assets for the UI."""

    assets: list[dict[str, Any]] = []

    # Changed assets
    for impacted in result.impact.changed:
        node = result.graph.nodes.get(impacted.asset_id)
        if node is None:
            continue
        change_descriptions = list(impacted.evidence) if impacted.evidence else ["Asset modified"]
        assets.append({
            "name": impacted.asset_id,
            "type": _asset_type_label(node.asset_type),
            "changeType": "Changed",
            "risk": result.risk.level.value,
            "description": "; ".join(change_descriptions),
            "impactType": ImpactType.CHANGED.value,
            "distance": 0,
        })

    # Directly affected
    for impacted in result.impact.directly_affected:
        node = result.graph.nodes.get(impacted.asset_id)
        if node is None or node.external:
            continue
        assets.append({
            "name": impacted.asset_id,
            "type": _asset_type_label(node.asset_type),
            "changeType": "Directly affected",
            "risk": "Medium" if result.risk.level.value in ("High", "Critical") else "Low",
            "description": impacted.reason,
            "impactType": ImpactType.DIRECTLY_AFFECTED.value,
            "distance": impacted.distance,
        })

    # Transitively affected
    for impacted in result.impact.transitively_affected:
        node = result.graph.nodes.get(impacted.asset_id)
        if node is None or node.external:
            continue
        assets.append({
            "name": impacted.asset_id,
            "type": _asset_type_label(node.asset_type),
            "changeType": "Transitively affected",
            "risk": "Low",
            "description": impacted.reason,
            "impactType": ImpactType.TRANSITIVELY_AFFECTED.value,
            "distance": impacted.distance,
        })

    return assets


def _serialize_risk(result: AnalysisResult) -> dict[str, Any]:
    return {
        "level": result.risk.level.value,
        "score": result.risk.score,
        "drivers": [d.description for d in result.risk.drivers],
    }


def _serialize_dependencies(result: AnalysisResult) -> dict[str, Any]:
    """Serialize the dependency graph for the UI.

    Filters to only include internal package nodes and edges
    that are part of the impact path.
    """

    impacted_ids = {a.asset_id for a in result.impact.all_impacted}
    relevant_nodes: dict[str, dict[str, Any]] = {}
    relevant_edges: list[dict[str, Any]] = []

    for node_id, node in result.graph.nodes.items():
        if node.external:
            continue
        if node_id not in impacted_ids:
            continue
        relevant_nodes[node_id] = {
            "id": node_id,
            "label": node.asset_name,
            "type": _asset_type_label(node.asset_type),
            "highlight": node.changed,
        }

    for edge in result.graph.edges:
        if edge.source_id in relevant_nodes and edge.target_id in relevant_nodes:
            relevant_edges.append({
                "from": edge.source_id,
                "to": edge.target_id,
                "label": _edge_label(edge.edge_type),
            })

    return {
        "nodes": list(relevant_nodes.values()),
        "edges": relevant_edges,
    }


def _serialize_tests(result: AnalysisResult) -> list[dict[str, Any]]:
    return [
        {
            "name": rec.name,
            "priority": rec.priority.value,
            "scenario": rec.scenario,
        }
        for rec in result.recommendations
    ]


def _serialize_changes(result: AnalysisResult) -> list[dict[str, Any]]:
    """Detailed change list (extension beyond the mock contract)."""
    return [
        {
            "type": change.change_type.value,
            "asset": change.affected_asset.asset_id,
            "description": change.description,
            "metadata": dict(change.metadata) if change.metadata else {},
        }
        for change in result.comparison.changes
    ]


def _serialize_impact(result: AnalysisResult) -> list[dict[str, Any]]:
    """Serialized impact list (extension beyond the mock contract)."""
    return [
        {
            "asset": impacted.asset_id,
            "impactType": impacted.impact_type.value,
            "distance": impacted.distance,
            "reason": impacted.reason,
        }
        for impacted in result.impact.all_impacted
    ]


def _asset_type_label(asset_type: AssetType) -> str:
    """Human-readable label for an asset type."""
    labels = {
        AssetType.FLOW_SERVICE: "Flow Service",
        AssetType.DOCUMENT_TYPE: "Document Type",
        AssetType.ADAPTER_SERVICE: "Adapter Service",
        AssetType.MAP_SERVICE: "Map Service",
        AssetType.SCHEDULER_SERVICE: "Scheduler Service",
        AssetType.SQL_FIXTURE: "SQL fixture",
        AssetType.UNKNOWN: "Unknown",
    }
    return labels.get(asset_type, asset_type.value)


def _edge_label(edge_type: EdgeType) -> str:
    return "invokes" if edge_type == EdgeType.INVOCATION else "maps into"


def _json_default(obj: Any) -> Any:
    """Fallback serializer for types json.dumps doesn't handle natively."""
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
