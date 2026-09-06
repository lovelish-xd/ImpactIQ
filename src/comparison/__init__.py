"""Git snapshot loading and deterministic comparison entry points."""

from .git_snapshot import GitRevisionReader, GitSnapshotError, RevisionAssets, load_revision_assets
from .snapshots import ComparisonResult, compare_revision_assets, compare_revisions, compare_snapshots

__all__ = [
    "ComparisonResult",
    "GitRevisionReader",
    "GitSnapshotError",
    "RevisionAssets",
    "compare_revision_assets",
    "compare_revisions",
    "compare_snapshots",
    "load_revision_assets",
]
