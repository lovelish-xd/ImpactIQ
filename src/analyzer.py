"""ImpactIQ analyzer — orchestrates the full analysis pipeline.

Pipeline:
  Git → Parse → Compare → Dependency Graph → Impact → Risk → Recommendations → Result
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

from src.comparison import ComparisonResult, compare_revisions
from src.dependency import DependencyGraph, build_dependency_graph
from src.impact import ImpactResult, analyze_impact
from src.recommendations import TestRecommendation, generate_recommendations
from src.risk import RiskResult, calculate_risk


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Complete analysis result from the ImpactIQ pipeline."""

    repository_path: str
    package_path: str
    base_revision: str
    target_revision: str
    comparison: ComparisonResult
    graph: DependencyGraph
    impact: ImpactResult
    risk: RiskResult
    recommendations: tuple[TestRecommendation, ...]


def analyze(
    repository_path: str | Path,
    package_path: str | Path,
    base_revision: str,
    target_revision: str,
) -> AnalysisResult:
    """Run the full ImpactIQ analysis pipeline.

    Orchestrates:
    1. Git snapshot comparison (parse both revisions, compare)
    2. Dependency graph construction (from target revision assets + changes)
    3. Impact analysis (BFS upstream from changed assets)
    4. Risk scoring (rule-based, deterministic)
    5. Regression test recommendations

    Returns a single AnalysisResult containing all analysis data.
    """

    comparison = compare_revisions(
        repository_path, package_path, base_revision, target_revision,
    )

    graph = build_dependency_graph(
        comparison.target_assets,
        changes=comparison.changes,
    )

    impact = analyze_impact(graph)
    risk = calculate_risk(comparison, impact, graph)
    recommendations = generate_recommendations(comparison, impact, graph)

    return AnalysisResult(
        repository_path=str(repository_path),
        package_path=str(package_path),
        base_revision=base_revision,
        target_revision=target_revision,
        comparison=comparison,
        graph=graph,
        impact=impact,
        risk=risk,
        recommendations=recommendations,
    )
