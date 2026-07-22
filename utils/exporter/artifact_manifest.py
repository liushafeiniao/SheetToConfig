"""Deterministic runtime artifact manifests for hot-update clients."""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping


MANIFEST_NAME = "excel2json-manifest.json"
MANIFEST_VERSION = 1
RUNTIME_FORMATS = {"json", "lua", "pb"}


def _normal_path(value: str) -> str:
    normalized = str(value).replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"Invalid manifest path: {value}")
    return path.as_posix()


@dataclass(frozen=True)
class ArtifactRecord:
    platform: str
    path: str
    format: str
    sha256: str
    size: int
    workbook: str
    sheet: str

    @classmethod
    def from_bytes(cls, platform: str, path: str, format: str, payload: bytes,
                   workbook: str, sheet: str) -> "ArtifactRecord":
        return cls(
            platform=platform,
            path=_normal_path(path),
            format=format.lower(),
            sha256=hashlib.sha256(payload).hexdigest(),
            size=len(payload),
            workbook=os.path.basename(workbook),
            sheet=sheet,
        )

    @classmethod
    def from_file(cls, platform: str, root: str | Path, file_path: str | Path,
                  workbook: str, sheet: str) -> "ArtifactRecord":
        root_path = Path(root).resolve()
        target = Path(file_path).resolve()
        try:
            relative = target.relative_to(root_path).as_posix()
        except ValueError as exc:
            raise ValueError(f"Artifact is outside output root: {target}") from exc
        payload = target.read_bytes()
        return cls.from_bytes(
            platform, relative, target.suffix.lstrip('.'), payload, workbook, sheet
        )

    def to_manifest_entry(self) -> dict:
        if self.format not in RUNTIME_FORMATS:
            raise ValueError(f"Unsupported runtime format: {self.format}")
        return {
            "path": _normal_path(self.path),
            "format": self.format,
            "sha256": self.sha256,
            "size": self.size,
            "source": {"workbook": self.workbook, "sheet": self.sheet},
        }


def _content_version(files: list[dict]) -> str:
    identities = [
        {
            "path": item["path"], "format": item["format"],
            "sha256": item["sha256"], "size": item["size"],
        }
        for item in files
    ]
    payload = json.dumps(
        identities, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_manifest(platform: str, records: Iterable[ArtifactRecord]) -> dict:
    entries = []
    seen = set()
    for record in records:
        if record.platform != platform:
            raise ValueError(f"Artifact platform mismatch: {record.platform} != {platform}")
        entry = record.to_manifest_entry()
        if entry["path"] in seen:
            raise ValueError(f"Duplicate artifact path: {entry['path']}")
        seen.add(entry["path"])
        entries.append(entry)
    entries.sort(key=lambda item: item["path"])
    return {
        "manifestVersion": MANIFEST_VERSION,
        "platform": platform,
        "contentVersion": _content_version(entries),
        "files": entries,
    }


def canonical_manifest_bytes(manifest: Mapping) -> bytes:
    validate_manifest(manifest)
    return (
        json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ) + "\n"
    ).encode("utf-8")


def validate_manifest(manifest: Mapping, expected_platform: str = "") -> None:
    if not isinstance(manifest, Mapping):
        raise ValueError("Manifest must be a JSON object")
    if manifest.get("manifestVersion") != MANIFEST_VERSION:
        raise ValueError(f"Unknown manifest version: {manifest.get('manifestVersion')}")
    platform = manifest.get("platform")
    if platform not in ("client", "server"):
        raise ValueError(f"Invalid manifest platform: {platform}")
    if expected_platform and platform != expected_platform:
        raise ValueError(f"Manifest platform mismatch: {platform} != {expected_platform}")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("Manifest files must be an array")
    seen = set()
    for item in files:
        if not isinstance(item, Mapping):
            raise ValueError("Manifest file entry must be an object")
        path = _normal_path(item.get("path", ""))
        if path in seen:
            raise ValueError(f"Duplicate manifest path: {path}")
        seen.add(path)
        if item.get("format") not in RUNTIME_FORMATS:
            raise ValueError(f"Unsupported manifest format: {item.get('format')}")
        digest = item.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"Invalid sha256 for {path}")
        if not isinstance(item.get("size"), int) or item["size"] < 0:
            raise ValueError(f"Invalid size for {path}")
        source = item.get("source")
        if not isinstance(source, Mapping) or not source.get("workbook") or not source.get("sheet"):
            raise ValueError(f"Invalid source for {path}")
    if manifest.get("contentVersion") != _content_version(sorted(files, key=lambda item: item["path"])):
        raise ValueError("Manifest contentVersion does not match files")


def load_manifest(path: str | Path, expected_platform: str) -> dict:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read manifest: {path}: {exc}") from exc
    validate_manifest(manifest, expected_platform)
    return manifest


def diff_manifests(old: Mapping | None, new: Mapping) -> dict:
    old_files = {item["path"]: item for item in (old or {}).get("files", [])}
    new_files = {item["path"]: item for item in new.get("files", [])}
    added = sorted(set(new_files) - set(old_files))
    removed = sorted(set(old_files) - set(new_files))
    modified = sorted(
        path for path in set(old_files) & set(new_files)
        if any(old_files[path].get(key) != new_files[path].get(key)
               for key in ("format", "sha256", "size"))
    )
    return {"added": added, "modified": modified, "removed": removed}


def records_from_manifest(manifest: Mapping) -> list[ArtifactRecord]:
    records = []
    for item in manifest.get("files", []):
        source = item["source"]
        records.append(ArtifactRecord(
            platform=manifest["platform"], path=item["path"],
            format=item["format"], sha256=item["sha256"], size=item["size"],
            workbook=source["workbook"], sheet=source["sheet"],
        ))
    return records
