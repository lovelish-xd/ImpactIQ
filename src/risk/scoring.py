"""Deterministic, rule-based risk scoring for ImpactIQ analysis results.

Scoring rules and weights are documented inline and tested explicitly.
The score is computed entirely from detected changes, impact analysis,
and dependency graph structure — never from AI or hard-coded scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.comparison.snapshots import ComparisonResult
from src.dependency import DependencyGraph
from src.impact import ImpactResult, ImpactType
from src.models import ChangeType


class RiskLevel(str, Enum):
    """Risk classification derived from numeric score."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass(frozen=True, slots=True)
class RiskDriver:
    """One human-readable reason contributing to the risk score."""

    description: str
    points: int


@dataclass(frozen=True, slots=True)
class RiskResult:
    """Complete deterministic risk assessment."""

    score: int
    level: RiskLevel
    drivers: tuple[RiskDriver, ...]


# ── Scoring constants ──────────────────────────────────────────────
# Each rule adds points. Total is clamped to 0–100.

POINTS_ASSET_MODIFIED = 8          # per modified asset
POINTS_ASSET_ADDED = 5             # per added asset
POINTS_ASSET_REMOVED = 12          # per removed asset (breaking)

POINTS_FIELD_ADDED = 4             # per added field
POINTS_FIELD_REMOVED = 8           # per removed field (breaking)
POINTS_FIELD_MODIFIED = 6          # per modified field

POINTS_MAPPING_ADDED = 4           # per added mapping
POINTS_MAPPING_REMOVED = 8         # per removed mapping
POINTS_SIGNATURE_CHANGED = 10      # per signature change

POINTS_INVOCATION_ADDED = 5        # per new invocation
POINTS_INVOCATION_REMOVED = 10     # per removed invocation (breaking)

POINTS_SQL_CHANGED = 10            # per SQL change

POINTS_DIRECT_DEPENDENT = 5        # per directly affected asset
POINTS_TRANSITIVE_DEPENDENT = 2    # per transitively affected asset

# Thresholds for risk levels
THRESHOLD_LOW = 25
THRESHOLD_MEDIUM = 50
THRESHOLD_HIGH = 75
# Above HIGH → CRITICAL


def calculate_risk(
    comparison: ComparisonResult,
    impact: ImpactResult,
    graph: DependencyGraph | None = None,
) -> RiskResult:
    """Compute a deterministic risk score from comparison and impact data."""

    drivers: list[RiskDriver] = []

    # ── Asset-level changes ────────────────────────────────────────
    if comparison.modified_assets:
        pts = len(comparison.modified_assets) * POINTS_ASSET_MODIFIED
        drivers.append(RiskDriver(
            description=f"{len(comparison.modified_assets)} asset(s) modified",
            points=pts,
        ))

    if comparison.added_assets:
        pts = len(comparison.added_assets) * POINTS_ASSET_ADDED
        drivers.append(RiskDriver(
            description=f"{len(comparison.added_assets)} asset(s) added",
            points=pts,
        ))

    if comparison.removed_assets:
        pts = len(comparison.removed_assets) * POINTS_ASSET_REMOVED
        drivers.append(RiskDriver(
            description=f"{len(comparison.removed_assets)} asset(s) removed",
            points=pts,
        ))

    # ── Change-type breakdown ──────────────────────────────────────
    change_counts: dict[ChangeType, int] = {}
    for change in comparison.changes:
        change_counts[change.change_type] = change_counts.get(change.change_type, 0) + 1

    _add_change_driver(drivers, change_counts, ChangeType.FIELD_ADDED,
                       POINTS_FIELD_ADDED, "field(s) added")
    _add_change_driver(drivers, change_counts, ChangeType.FIELD_REMOVED,
                       POINTS_FIELD_REMOVED, "field(s) removed")
    _add_change_driver(drivers, change_counts, ChangeType.FIELD_MODIFIED,
                       POINTS_FIELD_MODIFIED, "field(s) modified")
    _add_change_driver(drivers, change_counts, ChangeType.MAPPING_ADDED,
                       POINTS_MAPPING_ADDED, "mapping(s) added")
    _add_change_driver(drivers, change_counts, ChangeType.MAPPING_REMOVED,
                       POINTS_MAPPING_REMOVED, "mapping(s) removed")
    _add_change_driver(drivers, change_counts, ChangeType.SIGNATURE_CHANGED,
                       POINTS_SIGNATURE_CHANGED, "signature(s) changed")
    _add_change_driver(drivers, change_counts, ChangeType.INVOCATION_ADDED,
                       POINTS_INVOCATION_ADDED, "invocation(s) added")
    _add_change_driver(drivers, change_counts, ChangeType.INVOCATION_REMOVED,
                       POINTS_INVOCATION_REMOVED, "invocation(s) removed")

    # SQL changes come as MODIFIED with component=sql metadata
    sql_count = sum(
        1 for c in comparison.changes
        if c.metadata.get("component") == "sql"
    )
    if sql_count:
        pts = sql_count * POINTS_SQL_CHANGED
        drivers.append(RiskDriver(
            description=f"{sql_count} SQL statement(s) changed",
            points=pts,
        ))

    # ── Impact breadth ─────────────────────────────────────────────
    if impact.directly_affected:
        pts = len(impact.directly_affected) * POINTS_DIRECT_DEPENDENT
        drivers.append(RiskDriver(
            description=f"{len(impact.directly_affected)} directly affected dependent(s)",
            points=pts,
        ))

    if impact.transitively_affected:
        pts = len(impact.transitively_affected) * POINTS_TRANSITIVE_DEPENDENT
        drivers.append(RiskDriver(
            description=f"{len(impact.transitively_affected)} transitively affected dependent(s)",
            points=pts,
        ))

    # ── Compute final score ────────────────────────────────────────
    raw_score = sum(d.points for d in drivers)
    clamped = max(0, min(100, raw_score))
    level = _level_for_score(clamped)

    return RiskResult(
        score=clamped,
        level=level,
        drivers=tuple(drivers),
    )


def _add_change_driver(
    drivers: list[RiskDriver],
    counts: dict[ChangeType, int],
    change_type: ChangeType,
    points_each: int,
    label: str,
) -> None:
    count = counts.get(change_type, 0)
    if count > 0:
        drivers.append(RiskDriver(
            description=f"{count} {label}",
            points=count * points_each,
        ))


def _level_for_score(score: int) -> RiskLevel:
    if score < THRESHOLD_LOW:
        return RiskLevel.LOW
    if score < THRESHOLD_MEDIUM:
        return RiskLevel.MEDIUM
    if score < THRESHOLD_HIGH:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL
