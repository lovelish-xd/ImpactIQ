"""Deterministic regression test recommendations derived from analysis facts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from src.comparison.snapshots import ComparisonResult
from src.dependency import DependencyGraph, EdgeType
from src.impact import ImpactResult, ImpactType
from src.models import AssetType, ChangeType


class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass(frozen=True, slots=True)
class TestRecommendation:
    """One recommended regression test."""

    id: str
    priority: Priority
    name: str
    scenario: str
    related_assets: tuple[str, ...]
    reason: str


def generate_recommendations(
    comparison: ComparisonResult,
    impact: ImpactResult,
    graph: DependencyGraph,
) -> tuple[TestRecommendation, ...]:
    """Generate test recommendations from detected changes and impact.

    Rules:
    1. For each changed asset, recommend testing its direct functionality.
    2. For field/signature additions, recommend input-path testing.
    3. For mapping additions/changes, recommend data-flow testing.
    4. For SQL changes, recommend persistence and error-handling tests.
    5. For directly affected assets, recommend invocation-path testing.
    6. For the end-to-end path, recommend a smoke test.
    """

    recommendations: list[TestRecommendation] = []
    seen_ids: set[str] = set()

    _counter = _IdCounter()

    # ── Per-change recommendations ─────────────────────────────────
    for change in comparison.changes:
        aid = change.affected_asset.asset_id
        aname = change.affected_asset.name
        atype = change.affected_asset.asset_type

        if change.change_type == ChangeType.FIELD_ADDED:
            field_name = change.after.name if change.after else "unknown"
            rec_id = f"field-added-{aid}-{field_name}"
            if rec_id not in seen_ids:
                seen_ids.add(rec_id)
                recommendations.append(TestRecommendation(
                    id=_counter.next("field-input"),
                    priority=Priority.HIGH,
                    name=f"Verify {aname} accepts new field: {field_name}",
                    scenario=(
                        f"Invoke {aname} with the new {field_name} field populated "
                        f"and verify it is processed correctly."
                    ),
                    related_assets=(aid,),
                    reason=f"New input field {field_name} added to {aname}",
                ))

        elif change.change_type == ChangeType.FIELD_REMOVED:
            field_name = change.before.name if change.before else "unknown"
            rec_id = f"field-removed-{aid}-{field_name}"
            if rec_id not in seen_ids:
                seen_ids.add(rec_id)
                recommendations.append(TestRecommendation(
                    id=_counter.next("field-removal"),
                    priority=Priority.HIGH,
                    name=f"Verify {aname} without removed field: {field_name}",
                    scenario=(
                        f"Verify that {aname} works correctly without the previously "
                        f"required {field_name} field."
                    ),
                    related_assets=(aid,),
                    reason=f"Field {field_name} removed from {aname}",
                ))

        elif change.change_type == ChangeType.MAPPING_ADDED:
            if change.after is not None:
                src = _short_field(change.after.source_path)
                tgt = _short_field(change.after.target_path)
                rec_id = f"mapping-added-{aid}-{src}-{tgt}"
                if rec_id not in seen_ids:
                    seen_ids.add(rec_id)
                    recommendations.append(TestRecommendation(
                        id=_counter.next("mapping"),
                        priority=Priority.HIGH,
                        name=f"Verify data mapping: {src} → {tgt}",
                        scenario=(
                            f"In {aname}, verify that {src} is correctly "
                            f"mapped to {tgt} during execution."
                        ),
                        related_assets=(aid,),
                        reason=f"New mapping added in {aname}",
                    ))

        elif change.change_type == ChangeType.MAPPING_REMOVED:
            if change.before is not None:
                src = _short_field(change.before.source_path)
                tgt = _short_field(change.before.target_path)
                rec_id = f"mapping-removed-{aid}-{src}-{tgt}"
                if rec_id not in seen_ids:
                    seen_ids.add(rec_id)
                    recommendations.append(TestRecommendation(
                        id=_counter.next("mapping-removal"),
                        priority=Priority.HIGH,
                        name=f"Verify removed mapping does not break: {src} → {tgt}",
                        scenario=(
                            f"Verify that {aname} works correctly without the "
                            f"mapping from {src} to {tgt}."
                        ),
                        related_assets=(aid,),
                        reason=f"Mapping removed from {aname}",
                    ))

        # SQL changes
        if change.metadata.get("component") == "sql" and change.change_type == ChangeType.MODIFIED:
            rec_id = f"sql-{aid}"
            if rec_id not in seen_ids:
                seen_ids.add(rec_id)
                recommendations.append(TestRecommendation(
                    id=_counter.next("sql"),
                    priority=Priority.HIGH,
                    name=f"Verify database operation for {aname}",
                    scenario=(
                        f"Execute {aname} and verify the database operation "
                        f"succeeds with the updated SQL statement. "
                        f"Confirm parameter count and column alignment."
                    ),
                    related_assets=(aid,),
                    reason=f"SQL statement changed in {aname}",
                ))

    # ── Impact-based recommendations ───────────────────────────────
    for impacted in impact.directly_affected:
        rec_id = f"direct-{impacted.asset_id}"
        if rec_id not in seen_ids:
            seen_ids.add(rec_id)
            node = graph.nodes.get(impacted.asset_id)
            aname = node.asset_name if node else impacted.asset_id
            # Find which changed services it depends on
            changed_deps = []
            for edge in graph.dependencies_of(impacted.asset_id):
                if edge.target_id in graph.changed_node_ids():
                    dep_node = graph.nodes.get(edge.target_id)
                    changed_deps.append(dep_node.asset_name if dep_node else edge.target_id)

            recommendations.append(TestRecommendation(
                id=_counter.next("invocation"),
                priority=Priority.MEDIUM,
                name=f"Verify {aname} invocation path",
                scenario=(
                    f"Invoke {aname} and verify it correctly calls "
                    f"{', '.join(changed_deps) if changed_deps else 'its dependencies'} "
                    f"with the updated interface."
                ),
                related_assets=(impacted.asset_id,),
                reason=impacted.reason,
            ))

    # ── End-to-end smoke test ──────────────────────────────────────
    if impact.transitively_affected:
        # Find the entry point (deepest transitive) for smoke test
        entry = max(impact.transitively_affected, key=lambda a: a.distance)
        entry_node = graph.nodes.get(entry.asset_id)
        entry_name = entry_node.asset_name if entry_node else entry.asset_id
        changed_names = [
            graph.nodes[a.asset_id].asset_name
            for a in impact.changed
            if a.asset_id in graph.nodes
        ]
        rec_id = f"e2e-{entry.asset_id}"
        if rec_id not in seen_ids:
            seen_ids.add(rec_id)
            recommendations.append(TestRecommendation(
                id=_counter.next("e2e"),
                priority=Priority.MEDIUM,
                name=f"End-to-end: {entry_name} → changed services",
                scenario=(
                    f"Invoke {entry_name} and verify the full execution path "
                    f"reaches {', '.join(changed_names)} with correct behavior."
                ),
                related_assets=(entry.asset_id, *(a.asset_id for a in impact.changed)),
                reason=f"Transitive impact path from {entry_name} to changed services",
            ))

    # ── Null/missing-value test for added fields ───────────────────
    for change in comparison.changes:
        if change.change_type == ChangeType.FIELD_ADDED and change.after:
            field_name = change.after.name
            aid = change.affected_asset.asset_id
            aname = change.affected_asset.name
            rec_id = f"null-{aid}-{field_name}"
            if rec_id not in seen_ids:
                seen_ids.add(rec_id)
                recommendations.append(TestRecommendation(
                    id=_counter.next("null-handling"),
                    priority=Priority.MEDIUM,
                    name=f"Verify {aname} handles missing {field_name}",
                    scenario=(
                        f"Invoke {aname} without providing {field_name} "
                        f"and verify expected null/default behavior."
                    ),
                    related_assets=(aid,),
                    reason=f"New field {field_name} may be optional or nullable",
                ))

    return tuple(recommendations)


class _IdCounter:
    """Simple counter for generating unique recommendation IDs."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def next(self, prefix: str) -> str:
        self._counts[prefix] = self._counts.get(prefix, 0) + 1
        return f"{prefix}-{self._counts[prefix]}"


def _short_field(path: str) -> str:
    """Extract a human-readable field name from a mapping path."""
    stripped = path.lstrip("/")
    return stripped.split(";")[0] if ";" in stripped else stripped
