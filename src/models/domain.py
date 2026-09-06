"""Parser-independent domain models for ImpactIQ analyzer data."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping as ReadOnlyMapping


class AssetType(str, Enum):
    """Known asset kinds represented by the current demo package."""

    FLOW_SERVICE = "flow_service"
    DOCUMENT_TYPE = "document_type"
    ADAPTER_SERVICE = "adapter_service"
    MAP_SERVICE = "map_service"
    SCHEDULER_SERVICE = "scheduler_service"
    SQL_FIXTURE = "sql_fixture"
    UNKNOWN = "unknown"


class ChangeType(str, Enum):
    """Deterministic change categories detected by future comparison logic."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    FIELD_ADDED = "field_added"
    FIELD_REMOVED = "field_removed"
    FIELD_MODIFIED = "field_modified"
    MAPPING_ADDED = "mapping_added"
    MAPPING_REMOVED = "mapping_removed"
    INVOCATION_ADDED = "invocation_added"
    INVOCATION_REMOVED = "invocation_removed"
    SIGNATURE_CHANGED = "signature_changed"


def _freeze_mapping(values: ReadOnlyMapping[str, str]) -> ReadOnlyMapping[str, str]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class Asset:
    """A stable webMethods package asset discovered from a repository snapshot."""

    asset_id: str
    name: str
    asset_type: AssetType
    package_path: str
    metadata: ReadOnlyMapping[str, str] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class Field:
    """A field from a service signature, document type, or adapter signature."""

    name: str
    datatype: str
    required: bool | None = None
    parent_path: str | None = None
    reference: str | None = None
    dimension: int | None = None
    children: tuple["Field", ...] = ()
    metadata: ReadOnlyMapping[str, str] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "children", tuple(self.children))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class ServiceSignature:
    """Input and output fields for a service-like asset."""

    inputs: tuple[Field, ...] = ()
    outputs: tuple[Field, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))


@dataclass(frozen=True, slots=True)
class Mapping:
    """A data movement instruction observed in a Flow Service."""

    source_path: str
    target_path: str
    mapping_type: str = "MAPCOPY"
    instruction: str | None = None
    metadata: ReadOnlyMapping[str, str] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class Invocation:
    """A service reference from one service-like asset to another."""

    source_service: str
    target_service: str
    reference_type: str = "INVOKE"
    metadata: ReadOnlyMapping[str, str] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class AssetSnapshot:
    """Parsed facts for one asset at one repository version."""

    asset: Asset
    signature: ServiceSignature | None = None
    fields: tuple[Field, ...] = ()
    mappings: tuple[Mapping, ...] = ()
    invocations: tuple[Invocation, ...] = ()
    facts: ReadOnlyMapping[str, str] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", tuple(self.fields))
        object.__setattr__(self, "mappings", tuple(self.mappings))
        object.__setattr__(self, "invocations", tuple(self.invocations))
        object.__setattr__(self, "facts", _freeze_mapping(self.facts))


@dataclass(frozen=True, slots=True)
class Change:
    """A deterministic difference between two asset snapshots."""

    change_type: ChangeType
    affected_asset: Asset
    description: str
    before: Any | None = None
    after: Any | None = None
    metadata: ReadOnlyMapping[str, str] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))
