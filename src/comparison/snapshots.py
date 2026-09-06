"""Deterministic comparison of parsed ImpactIQ asset snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.models import AssetSnapshot, Change, ChangeType, Field, Invocation, Mapping

from .git_snapshot import GitRevisionReader, RevisionAssets


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    """Comparison result for two parsed package snapshots."""

    base_revision: str
    target_revision: str
    base_assets: tuple[AssetSnapshot, ...]
    target_assets: tuple[AssetSnapshot, ...]
    added_assets: tuple[AssetSnapshot, ...]
    removed_assets: tuple[AssetSnapshot, ...]
    modified_assets: tuple[AssetSnapshot, ...]
    unchanged_assets: tuple[AssetSnapshot, ...]
    changes: tuple[Change, ...]


def compare_revisions(
    repository_path: str | Path,
    package_path: str | Path,
    base_revision: str,
    target_revision: str,
) -> ComparisonResult:
    """Load and compare one package across two Git revisions."""

    reader = GitRevisionReader(repository_path)
    base = reader.load_assets(base_revision, package_path)
    target = reader.load_assets(target_revision, package_path)
    return compare_revision_assets(base, target)


def compare_revision_assets(base: RevisionAssets, target: RevisionAssets) -> ComparisonResult:
    """Compare parsed assets that were already loaded from Git revisions."""

    return compare_snapshots(
        base.assets,
        target.assets,
        base_revision=base.revision,
        target_revision=target.revision,
    )


def compare_snapshots(
    base_assets: Iterable[AssetSnapshot],
    target_assets: Iterable[AssetSnapshot],
    *,
    base_revision: str = "",
    target_revision: str = "",
) -> ComparisonResult:
    """Compare two sets of AssetSnapshots by stable asset identity."""

    base_by_id = {snapshot.asset.asset_id: snapshot for snapshot in base_assets}
    target_by_id = {snapshot.asset.asset_id: snapshot for snapshot in target_assets}

    added_ids = sorted(target_by_id.keys() - base_by_id.keys())
    removed_ids = sorted(base_by_id.keys() - target_by_id.keys())
    common_ids = sorted(base_by_id.keys() & target_by_id.keys())

    added_assets = tuple(target_by_id[asset_id] for asset_id in added_ids)
    removed_assets = tuple(base_by_id[asset_id] for asset_id in removed_ids)
    modified_assets: list[AssetSnapshot] = []
    unchanged_assets: list[AssetSnapshot] = []
    changes: list[Change] = []

    for snapshot in added_assets:
        changes.append(
            Change(
                change_type=ChangeType.ADDED,
                affected_asset=snapshot.asset,
                before=None,
                after=snapshot,
                description=f"Asset added: {snapshot.asset.asset_id}",
            )
        )

    for snapshot in removed_assets:
        changes.append(
            Change(
                change_type=ChangeType.REMOVED,
                affected_asset=snapshot.asset,
                before=snapshot,
                after=None,
                description=f"Asset removed: {snapshot.asset.asset_id}",
            )
        )

    for asset_id in common_ids:
        base_snapshot = base_by_id[asset_id]
        target_snapshot = target_by_id[asset_id]
        if base_snapshot == target_snapshot:
            unchanged_assets.append(target_snapshot)
            continue

        modified_assets.append(target_snapshot)
        changes.append(
            Change(
                change_type=ChangeType.MODIFIED,
                affected_asset=target_snapshot.asset,
                before=base_snapshot,
                after=target_snapshot,
                description=f"Asset modified: {asset_id}",
            )
        )
        changes.extend(_compare_fields(base_snapshot, target_snapshot))
        changes.extend(_compare_mappings(base_snapshot, target_snapshot))
        changes.extend(_compare_invocations(base_snapshot, target_snapshot))
        changes.extend(_compare_sql(base_snapshot, target_snapshot))

    return ComparisonResult(
        base_revision=base_revision,
        target_revision=target_revision,
        base_assets=tuple(base_by_id[asset_id] for asset_id in sorted(base_by_id)),
        target_assets=tuple(target_by_id[asset_id] for asset_id in sorted(target_by_id)),
        added_assets=added_assets,
        removed_assets=removed_assets,
        modified_assets=tuple(modified_assets),
        unchanged_assets=tuple(unchanged_assets),
        changes=tuple(changes),
    )


def _compare_fields(base: AssetSnapshot, target: AssetSnapshot) -> list[Change]:
    changes: list[Change] = []
    for scope, base_fields, target_fields in _field_scopes(base, target):
        base_by_key = _field_map(base_fields)
        target_by_key = _field_map(target_fields)

        for key in sorted(target_by_key.keys() - base_by_key.keys()):
            field = target_by_key[key]
            changes.append(
                Change(
                    change_type=ChangeType.FIELD_ADDED,
                    affected_asset=target.asset,
                    before=None,
                    after=field,
                    description=f"Field added in {scope}: {key}",
                    metadata={"scope": scope, "field": key},
                )
            )

        for key in sorted(base_by_key.keys() - target_by_key.keys()):
            field = base_by_key[key]
            changes.append(
                Change(
                    change_type=ChangeType.FIELD_REMOVED,
                    affected_asset=base.asset,
                    before=field,
                    after=None,
                    description=f"Field removed from {scope}: {key}",
                    metadata={"scope": scope, "field": key},
                )
            )

        for key in sorted(base_by_key.keys() & target_by_key.keys()):
            base_field = base_by_key[key]
            target_field = target_by_key[key]
            field_changes = _field_value_changes(base_field, target_field)
            if not field_changes:
                continue
            changes.append(
                Change(
                    change_type=ChangeType.FIELD_MODIFIED,
                    affected_asset=target.asset,
                    before=base_field,
                    after=target_field,
                    description=f"Field modified in {scope}: {key}",
                    metadata={"scope": scope, "field": key, "changed": ",".join(field_changes)},
                )
            )

    return changes


def _field_scopes(
    base: AssetSnapshot,
    target: AssetSnapshot,
) -> tuple[tuple[str, tuple[Field, ...], tuple[Field, ...]], ...]:
    scopes: list[tuple[str, tuple[Field, ...], tuple[Field, ...]]] = []
    if base.fields or target.fields:
        scopes.append(("fields", base.fields, target.fields))

    if base.signature is not None or target.signature is not None:
        base_inputs = base.signature.inputs if base.signature is not None else ()
        target_inputs = target.signature.inputs if target.signature is not None else ()
        base_outputs = base.signature.outputs if base.signature is not None else ()
        target_outputs = target.signature.outputs if target.signature is not None else ()
        scopes.append(("signature.inputs", base_inputs, target_inputs))
        scopes.append(("signature.outputs", base_outputs, target_outputs))

    return tuple(scopes)


def _field_map(fields: tuple[Field, ...]) -> dict[str, Field]:
    mapped: dict[str, Field] = {}

    def visit(field: Field, path_prefix: str = "") -> None:
        path = f"{path_prefix}/{field.name}" if path_prefix else field.name
        mapped[path] = field
        for child in field.children:
            visit(child, path)

    for field in fields:
        visit(field)
    return mapped


def _field_value_changes(base: Field, target: Field) -> tuple[str, ...]:
    changed: list[str] = []
    if base.datatype != target.datatype:
        changed.append("datatype")
    if base.required is not None or target.required is not None:
        if base.required != target.required:
            changed.append("required")
    return tuple(changed)


def _compare_mappings(base: AssetSnapshot, target: AssetSnapshot) -> list[Change]:
    return _compare_ordered_facts(
        base.mappings,
        target.mappings,
        affected_asset=target.asset,
        added_type=ChangeType.MAPPING_ADDED,
        removed_type=ChangeType.MAPPING_REMOVED,
        modified_type=ChangeType.MODIFIED,
        label="mapping",
        exact_key=_mapping_key,
        order_key=_ordered_mapping_key,
        description_value=_mapping_description_value,
    )


def _compare_invocations(base: AssetSnapshot, target: AssetSnapshot) -> list[Change]:
    return _compare_ordered_facts(
        base.invocations,
        target.invocations,
        affected_asset=target.asset,
        added_type=ChangeType.INVOCATION_ADDED,
        removed_type=ChangeType.INVOCATION_REMOVED,
        modified_type=ChangeType.MODIFIED,
        label="invocation",
        exact_key=_invocation_key,
        order_key=_ordered_invocation_key,
        description_value=lambda invocation: invocation.target_service,
    )


def _compare_ordered_facts(
    base_values: tuple[Any, ...],
    target_values: tuple[Any, ...],
    *,
    affected_asset,
    added_type: ChangeType,
    removed_type: ChangeType,
    modified_type: ChangeType,
    label: str,
    exact_key,
    order_key,
    description_value,
) -> list[Change]:
    changes: list[Change] = []
    base_by_exact = {exact_key(value): value for value in base_values}
    target_by_exact = {exact_key(value): value for value in target_values}
    removed_exact = set(base_by_exact) - set(target_by_exact)
    added_exact = set(target_by_exact) - set(base_by_exact)

    changed_order_keys: set[tuple[str, str | None]] = set()
    if len(removed_exact) == len(added_exact):
        removed_by_order = {
            order_key(base_by_exact[key]): base_by_exact[key]
            for key in removed_exact
        }
        added_by_order = {
            order_key(target_by_exact[key]): target_by_exact[key]
            for key in added_exact
        }
        for key in sorted(set(removed_by_order) & set(added_by_order)):
            before = removed_by_order[key]
            after = added_by_order[key]
            changed_order_keys.add(key)
            changes.append(
                Change(
                    change_type=modified_type,
                    affected_asset=affected_asset,
                    before=before,
                    after=after,
                    description=f"{label.title()} changed: {description_value(before)} -> {description_value(after)}",
                    metadata={"component": label},
                )
            )

    for key in sorted(added_exact):
        value = target_by_exact[key]
        if order_key(value) in changed_order_keys:
            continue
        changes.append(
            Change(
                change_type=added_type,
                affected_asset=affected_asset,
                before=None,
                after=value,
                description=f"{label.title()} added: {description_value(value)}",
            )
        )

    for key in sorted(removed_exact):
        value = base_by_exact[key]
        if order_key(value) in changed_order_keys:
            continue
        changes.append(
            Change(
                change_type=removed_type,
                affected_asset=affected_asset,
                before=value,
                after=None,
                description=f"{label.title()} removed: {description_value(value)}",
            )
        )

    return changes


def _mapping_key(mapping: Mapping) -> tuple[str, str, str, str | None]:
    return (mapping.mapping_type, mapping.source_path, mapping.target_path, mapping.instruction)


def _ordered_mapping_key(mapping: Mapping) -> tuple[str, str | None]:
    return (mapping.mapping_type, mapping.metadata.get("order"))


def _mapping_description_value(mapping: Mapping) -> str:
    return f"{mapping.source_path} -> {mapping.target_path}"


def _invocation_key(invocation: Invocation) -> tuple[str, str, str]:
    return (invocation.reference_type, invocation.source_service, invocation.target_service)


def _ordered_invocation_key(invocation: Invocation) -> tuple[str, str | None]:
    return (invocation.reference_type, invocation.metadata.get("order"))


def _compare_sql(base: AssetSnapshot, target: AssetSnapshot) -> list[Change]:
    before = base.facts.get("query_sql")
    after = target.facts.get("query_sql")
    if before == after:
        return []

    if before is None:
        description = "SQL added: query.sql"
    elif after is None:
        description = "SQL removed: query.sql"
    else:
        description = "SQL modified: query.sql"

    return [
        Change(
            change_type=ChangeType.MODIFIED,
            affected_asset=target.asset,
            before=before,
            after=after,
            description=description,
            metadata={"component": "sql", "fact": "query_sql"},
        )
    ]
