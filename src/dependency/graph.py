"""Dependency graph constructed from parsed ImpactIQ asset snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Iterable

from src.models import AssetSnapshot, AssetType, Change


class EdgeType(str, Enum):
    """Relationship types supported by the dependency graph."""

    INVOCATION = "invocation"
    MAPPING = "mapping"


@dataclass(frozen=True, slots=True)
class GraphNode:
    """A node in the dependency graph representing one asset."""

    asset_id: str
    asset_name: str
    asset_type: AssetType
    changed: bool = False
    changes: tuple[Change, ...] = ()
    external: bool = False


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """A directed edge in the dependency graph."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    label: str = ""
    metadata: dict[str, str] = dataclass_field(default_factory=dict)


@dataclass
class DependencyGraph:
    """Adjacency-list dependency graph built from parsed snapshots.

    Edges follow the invocation direction:
      source --invokes--> target
      source --maps-into--> target

    Terminology:
      - dependents_of(X)  = nodes that invoke/map-into X  (upstream callers)
      - dependencies_of(X) = nodes that X invokes/maps-into (downstream callees)
    """

    nodes: dict[str, GraphNode] = dataclass_field(default_factory=dict)
    edges: list[GraphEdge] = dataclass_field(default_factory=list)

    _outgoing: dict[str, list[GraphEdge]] = dataclass_field(
        default_factory=dict, repr=False,
    )
    _incoming: dict[str, list[GraphEdge]] = dataclass_field(
        default_factory=dict, repr=False,
    )

    def add_node(self, node: GraphNode) -> None:
        """Register a node. Overwrites if the same asset_id is added again."""
        self.nodes[node.asset_id] = node
        self._outgoing.setdefault(node.asset_id, [])
        self._incoming.setdefault(node.asset_id, [])

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed edge between two already-registered nodes."""
        self.edges.append(edge)
        self._outgoing.setdefault(edge.source_id, []).append(edge)
        self._incoming.setdefault(edge.target_id, []).append(edge)

    def dependencies_of(self, asset_id: str) -> list[GraphEdge]:
        """Edges where *asset_id* is the source (things it calls/maps into)."""
        return list(self._outgoing.get(asset_id, []))

    def dependents_of(self, asset_id: str) -> list[GraphEdge]:
        """Edges where *asset_id* is the target (things that call/map into it)."""
        return list(self._incoming.get(asset_id, []))

    def changed_node_ids(self) -> set[str]:
        """Return asset IDs of all nodes marked as changed."""
        return {nid for nid, node in self.nodes.items() if node.changed}


def build_dependency_graph(
    snapshots: Iterable[AssetSnapshot],
    changes: Iterable[Change] = (),
) -> DependencyGraph:
    """Build a dependency graph from parsed snapshots and optional changes.

    Only creates nodes for assets that exist in the provided snapshots.
    External service references (e.g. ``pub.flow:getLastError``) are
    recorded as external placeholder nodes so the graph does not silently
    lose information, but they are clearly marked ``external=True``.
    """

    graph = DependencyGraph()
    snapshots_by_id: dict[str, AssetSnapshot] = {}

    changed_ids: set[str] = set()
    changes_by_id: dict[str, list[Change]] = {}
    for change in changes:
        changed_ids.add(change.affected_asset.asset_id)
        changes_by_id.setdefault(change.affected_asset.asset_id, []).append(change)

    for snapshot in snapshots:
        aid = snapshot.asset.asset_id
        snapshots_by_id[aid] = snapshot
        graph.add_node(
            GraphNode(
                asset_id=aid,
                asset_name=snapshot.asset.name,
                asset_type=snapshot.asset.asset_type,
                changed=aid in changed_ids,
                changes=tuple(changes_by_id.get(aid, ())),
            )
        )

    for snapshot in snapshots_by_id.values():
        _add_invocation_edges(graph, snapshot, snapshots_by_id)
        _add_mapping_edges(graph, snapshot, snapshots_by_id)

    return graph


def _add_invocation_edges(
    graph: DependencyGraph,
    snapshot: AssetSnapshot,
    known: dict[str, AssetSnapshot],
) -> None:
    """Create edges for each INVOKE found in the snapshot."""

    source_id = snapshot.asset.asset_id
    for invocation in snapshot.invocations:
        target_id = invocation.target_service
        if target_id not in known:
            _ensure_external_node(graph, target_id)
        graph.add_edge(
            GraphEdge(
                source_id=source_id,
                target_id=target_id,
                edge_type=EdgeType.INVOCATION,
                label=f"invokes {_short_name(target_id)}",
                metadata=dict(invocation.metadata),
            )
        )


def _add_mapping_edges(
    graph: DependencyGraph,
    snapshot: AssetSnapshot,
    known: dict[str, AssetSnapshot],
) -> None:
    """Create mapping dependency edges where both endpoints are known assets.

    Mapping edges connect the *service containing the mapping* to the
    *target service whose input is being populated*, when that target
    service can be inferred from the mapping target path.
    """

    source_id = snapshot.asset.asset_id
    for mapping in snapshot.mappings:
        target_input_root = _extract_input_root(mapping.target_path)
        if target_input_root is None:
            continue
        target_asset_id = _resolve_input_root(target_input_root, known)
        if target_asset_id is None or target_asset_id == source_id:
            continue
        graph.add_edge(
            GraphEdge(
                source_id=source_id,
                target_id=target_asset_id,
                edge_type=EdgeType.MAPPING,
                label=f"maps {_short_field(mapping.source_path)} → {_short_field(mapping.target_path)}",
                metadata={"source_path": mapping.source_path, "target_path": mapping.target_path},
            )
        )


def _ensure_external_node(graph: DependencyGraph, asset_id: str) -> None:
    """Register an external (out-of-package) node if not already present."""

    if asset_id in graph.nodes:
        return
    graph.add_node(
        GraphNode(
            asset_id=asset_id,
            asset_name=_short_name(asset_id),
            asset_type=AssetType.UNKNOWN,
            external=True,
        )
    )


def _short_name(asset_id: str) -> str:
    """Extract the short service name from a fully-qualified asset id."""
    return asset_id.rsplit(":", 1)[-1] if ":" in asset_id else asset_id


def _extract_input_root(target_path: str) -> str | None:
    """Extract the top-level input document name from a mapping target path.

    Example: '/SaveOrderDBInput/customerEmail;1;0' -> 'SaveOrderDBInput'
    """

    path = target_path.lstrip("/")
    if not path:
        return None
    return path.split("/")[0].split(";")[0]


def _resolve_input_root(input_root: str, known: dict[str, AssetSnapshot]) -> str | None:
    """Try to match an input document root name to a known asset.

    Uses the naming convention where an adapter service ``FooDB`` has
    input root ``FooDBInput``.
    """

    for asset_id, snapshot in known.items():
        short = _short_name(asset_id)
        if input_root == f"{short}Input":
            return asset_id
    return None


def _short_field(path: str) -> str:
    """Extract a human-readable field reference from a mapping path."""
    stripped = path.lstrip("/")
    parts = stripped.split(";")[0] if ";" in stripped else stripped
    return parts
