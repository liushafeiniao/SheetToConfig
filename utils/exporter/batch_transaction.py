"""Prepare cross-platform artifact writes and hot-update manifests."""

from pathlib import Path
from typing import List

from .artifact_manifest import (
    MANIFEST_NAME,
    ArtifactRecord,
    build_manifest,
    canonical_manifest_bytes,
    diff_manifests,
    load_manifest,
    records_from_manifest,
)


class IncrementalManifestRequiredError(ValueError):
    """Raised when an incremental export cannot safely infer old ownership."""


def prepare_batch_commit(generated: List[dict], workbooks: List[str],
                         client_path: str, server_path: str, csharp_path: str,
                         mode: str, incremental: bool,
                         preserve_existing_formats=()) -> dict:
    actual_roots = {
        'client': Path(client_path).resolve() if client_path else None,
        'server': Path(server_path).resolve() if server_path else None,
        'csharp': Path(csharp_path).resolve() if csharp_path else None,
    }
    writes = {}
    runtime_records = {'client': [], 'server': []}
    public_artifacts = []

    for item in generated:
        stage_root = Path(item['root']).resolve()
        stage_path = Path(item['path']).resolve()
        relative = stage_path.relative_to(stage_root)
        platform = item['platform']
        actual_root = actual_roots.get(platform)
        if actual_root is None:
            raise ValueError(f"Output root is not configured for {platform}")
        destination = (actual_root / relative).resolve()
        try:
            destination.relative_to(actual_root)
        except ValueError as exc:
            raise ValueError(f"Artifact escapes output root: {destination}") from exc
        if destination in writes:
            raise ValueError(f"Output path conflict: {destination}")
        payload = stage_path.read_bytes()
        writes[destination] = payload

        if platform in runtime_records and item['format'] in ('json', 'lua', 'pb'):
            record = ArtifactRecord.from_bytes(
                platform, relative.as_posix(), item['format'], payload,
                item['workbook'], item['sheet'],
            )
            runtime_records[platform].append(record)
            public_artifacts.append(record.to_manifest_entry())

    changes = {}
    manifests = {}
    deletes = set()
    selected = {name.lower() for name in workbooks}
    for platform, marker in (('client', 'c'), ('server', 's')):
        if marker not in mode:
            continue
        root = actual_roots[platform]
        if root is None:
            raise ValueError(f"Output root is not configured for {platform}")
        manifest_path = root / MANIFEST_NAME
        old_manifest = None
        if manifest_path.exists():
            old_manifest = load_manifest(manifest_path, platform)
        elif incremental:
            raise IncrementalManifestRequiredError(
                f"Incremental export requires an existing manifest: {manifest_path}"
            )

        records = list(runtime_records[platform])
        old_records = records_from_manifest(old_manifest) if old_manifest else []
        if incremental:
            records = [
                record for record in old_records
                if record.workbook.lower() not in selected
            ] + records
        if preserve_existing_formats:
            generated_paths = {record.path for record in records}
            records = [
                record for record in old_records
                if record.format in preserve_existing_formats
                and record.path not in generated_paths
            ] + records
        new_manifest = build_manifest(platform, records)
        platform_changes = diff_manifests(old_manifest, new_manifest)
        for relative in platform_changes['removed']:
            stale = (root / Path(relative)).resolve()
            try:
                stale.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"Manifest path escapes output root: {relative}") from exc
            deletes.add(stale)
            if Path(relative).suffix.lower() == '.pb':
                # Protocol sources are owned companions but stay out of the
                # runtime hot-update manifest.
                deletes.add(stale.with_suffix('.proto'))
        writes[manifest_path] = canonical_manifest_bytes(new_manifest)
        changes[platform] = platform_changes
        manifests[platform] = new_manifest

    return {
        'writes': writes,
        'deletes': deletes,
        'artifacts': sorted(public_artifacts, key=lambda item: (item['path'], item['format'])),
        'changes': changes,
        'manifests': manifests,
    }
