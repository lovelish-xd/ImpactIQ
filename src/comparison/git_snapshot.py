"""Read webMethods package snapshots from Git revisions without checkout."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import subprocess
import tarfile
import tempfile
from typing import Iterator

from src.models import AssetSnapshot
from src.parser import parse_package


class GitSnapshotError(Exception):
    """Raised when a package snapshot cannot be loaded from Git."""


@dataclass(frozen=True, slots=True)
class RevisionAssets:
    """Parsed package assets for a single Git revision."""

    revision: str
    package_path: str
    assets: tuple[AssetSnapshot, ...]


class GitRevisionReader:
    """Load package contents from Git revisions using git archive."""

    def __init__(self, repository_path: str | Path) -> None:
        self.repository_path = Path(repository_path)
        if not self.repository_path.exists():
            raise GitSnapshotError(f"Repository path does not exist: {self.repository_path}")
        if not self.repository_path.is_dir():
            raise GitSnapshotError(f"Repository path is not a directory: {self.repository_path}")

    def load_assets(self, revision: str, package_path: str | Path) -> RevisionAssets:
        """Parse one package at one Git revision into AssetSnapshots."""

        normalized_package_path = _normalize_package_path(package_path)
        with self.package_at_revision(revision, normalized_package_path) as extracted_package:
            return RevisionAssets(
                revision=revision,
                package_path=normalized_package_path,
                assets=parse_package(extracted_package),
            )

    @contextmanager
    def package_at_revision(self, revision: str, package_path: str | Path) -> Iterator[Path]:
        """Extract a package from a Git revision to a temporary directory."""

        normalized_package_path = _normalize_package_path(package_path)
        archive = self._archive(revision, normalized_package_path)
        with tempfile.TemporaryDirectory(prefix="impactiq-git-") as temp_dir:
            temp_root = Path(temp_dir)
            _extract_archive(archive, temp_root)
            extracted_package = temp_root / normalized_package_path
            if not extracted_package.exists():
                raise GitSnapshotError(
                    f"Package path {normalized_package_path!r} was not found in revision {revision!r}"
                )
            yield extracted_package

    def _archive(self, revision: str, package_path: str) -> bytes:
        command = [
            "git",
            "-c",
            f"safe.directory={self.repository_path}",
            "archive",
            "--format=tar",
            revision,
            "--",
            package_path,
        ]
        result = subprocess.run(
            command,
            cwd=self.repository_path,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise GitSnapshotError(
                f"Unable to archive {package_path!r} at {revision!r}: "
                f"{result.stderr.decode(errors='replace').strip()}"
            )
        return result.stdout


def load_revision_assets(
    repository_path: str | Path,
    package_path: str | Path,
    revision: str,
) -> RevisionAssets:
    """Convenience function for loading parsed assets from one revision."""

    return GitRevisionReader(repository_path).load_assets(revision, package_path)


def _normalize_package_path(package_path: str | Path) -> str:
    normalized = Path(package_path).as_posix().strip("/")
    if not normalized or normalized in {".", ".."} or normalized.startswith("../"):
        raise GitSnapshotError(f"Invalid package path: {package_path!r}")
    return normalized


def _extract_archive(archive: bytes, destination: Path) -> None:
    with tarfile.open(fileobj=BytesIO(archive), mode="r:") as tar:
        for member in tar.getmembers():
            target = (destination / member.name).resolve()
            destination_root = destination.resolve()
            if not str(target).startswith(str(destination_root)):
                raise GitSnapshotError(f"Refusing to extract archive member outside temp dir: {member.name}")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(destination, filter="data")
        else:
            tar.extractall(destination)
