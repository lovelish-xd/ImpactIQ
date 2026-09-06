"""Deterministic impact analysis based on the dependency graph."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Iterable

from src.dependency import DependencyGraph, EdgeType


class ImpactType(str, Enum):
    """Classification of how an asset is affected by a change."""

    CHANGED = "changed"
    DIRECTLY_AFFECTED = "directly_affected"
    TRANSITIVELY_AFFECTED = "transitively_affected"


@dataclass(frozen=True, slots=True)
class ImpactedAsset:
    """One asset's impact assessment."""

    asset_id: str
    impact_type: ImpactType
    distance: int
    reason: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ImpactResult:
    """Complete impact analysis for a set of changes."""

    changed: tuple[ImpactedAsset, ...]
    directly_affected: tuple[ImpactedAsset, ...]
    transitively_affected: tuple[ImpactedAsset, ...]

    @property
    def all_impacted(self) -> tuple[ImpactedAsset, ...]:
        return self.changed + self.directly_affected + self.transitively_affected


def analyze_impact(graph: DependencyGraph) -> ImpactResult:
    """Determine impact by traversing upstream from every changed node.

    Direction semantics:
      If A --invokes--> B and B is CHANGED, then A is affected because
      it depends on B.  We traverse the graph *upstream* — following
      incoming edges (dependents_of) — to find callers of changed assets.

    - distance 0 = CHANGED
    - distance 1 = DIRECTLY_AFFECTED (immediate caller of a changed asset)
    - distance 2+ = TRANSITIVELY_AFFECTED
    """

    changed_ids = graph.changed_node_ids()
    if not changed_ids:
        return ImpactResult(changed=(), directly_affected=(), transitively_affected=())

    changed: list[ImpactedAsset] = []
    for cid in sorted(changed_ids):
        node = graph.nodes[cid]
        change_descriptions = [c.description for c in node.changes] if node.changes else []
        changed.append(
            ImpactedAsset(
                asset_id=cid,
                impact_type=ImpactType.CHANGED,
                distance=0,
                reason=f"Asset modified: {node.asset_name}",
                evidence=tuple(change_descriptions),
            )
        )

    # BFS upstream from every changed node
    visited: dict[str, int] = {cid: 0 for cid in changed_ids}
    # reason_map tracks the evidence chain for each visited node
    reason_map: dict[str, tuple[str, tuple[str, ...]]] = {}

    queue: list[tuple[str, int, str, str]] = []
    for cid in sorted(changed_ids):
        for edge in graph.dependents_of(cid):
            if edge.source_id not in changed_ids and not _is_external(graph, edge.source_id):
                queue.append((edge.source_id, 1, cid, edge.label))

    while queue:
        asset_id, distance, via_id, via_label = queue.pop(0)
        if asset_id in visited and visited[asset_id] <= distance:
            continue
        visited[asset_id] = distance

        via_node = graph.nodes.get(via_id)
        via_name = via_node.asset_name if via_node else via_id
        if distance == 1:
            reason = f"Invokes changed service {via_name}"
        else:
            reason = f"Transitively depends on {via_name} (distance {distance})"
        reason_map[asset_id] = (reason, (via_label,))

        for edge in graph.dependents_of(asset_id):
            next_id = edge.source_id
            if next_id in changed_ids or _is_external(graph, next_id):
                continue
            if next_id not in visited or visited[next_id] > distance + 1:
                queue.append((next_id, distance + 1, asset_id, edge.label))

    directly: list[ImpactedAsset] = []
    transitively: list[ImpactedAsset] = []

    for asset_id in sorted(visited):
        if asset_id in changed_ids:
            continue
        dist = visited[asset_id]
        reason, evidence = reason_map[asset_id]
        impact = ImpactedAsset(
            asset_id=asset_id,
            impact_type=ImpactType.DIRECTLY_AFFECTED if dist == 1 else ImpactType.TRANSITIVELY_AFFECTED,
            distance=dist,
            reason=reason,
            evidence=evidence,
        )
        if dist == 1:
            directly.append(impact)
        else:
            transitively.append(impact)

    return ImpactResult(
        changed=tuple(changed),
        directly_affected=tuple(directly),
        transitively_affected=tuple(transitively),
    )


def _is_external(graph: DependencyGraph, asset_id: str) -> bool:
    """Check whether a node is an external (out-of-package) reference."""
    node = graph.nodes.get(asset_id)
    return node is not None and node.external
