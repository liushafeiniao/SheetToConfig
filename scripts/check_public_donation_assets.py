"""Check public inputs for exact private donation-asset leakage.

This local, read-only checker catches direct copies, common encodings and exact
decoded PNG pixels.  It is targeted evidence, not proof against arbitrary
lossy re-encodes or manually transformed images.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import tarfile
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


MAX_MANIFEST_BYTES = 16 * 1024
MAX_PRIVATE_FILE_BYTES = 2 * 1024 * 1024
MAX_CANDIDATE_FILE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_FILE_BYTES = 64 * 1024 * 1024
MAX_FILES = 10_000
MAX_PATH_CHARS = 4_096
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class PrivateAsset:
    name: str
    data: bytes
    sha256: str
    pixels: bytes | None
    qr_payload: str | None


def _read_limited(path: Path, limit: int) -> bytes:
    try:
        if path.stat().st_size > limit:
            raise ValueError("file exceeds the supported size limit")
        return path.read_bytes()
    except OSError as exc:
        raise ValueError("cannot read supplied path") from exc


def _safe_child(root: Path, path: Path, label: str) -> Path:
    if len(str(path)) > MAX_PATH_CHARS:
        raise ValueError(f"{label} path exceeds the supported limit")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} path escapes its supplied root") from exc
    return path


def _validate_manifest(private_dir: Path, manifest_path: Path) -> list[PrivateAsset]:
    raw = _read_limited(manifest_path, MAX_MANIFEST_BYTES)
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest must be valid UTF-8 JSON") from exc
    if set(manifest) != {"version", "files"} or manifest["version"] != 1:
        raise ValueError("manifest has an unsupported structure")
    files = manifest["files"]
    expected_names = {"alipay.png", "wechat.png"}
    if not isinstance(files, dict) or set(files) != expected_names:
        raise ValueError("manifest must name exactly the expected donation files")

    assets: list[PrivateAsset] = []
    for name in sorted(expected_names):
        record = files[name]
        if not isinstance(record, dict) or set(record) != {"sha256", "size", "width", "height"}:
            raise ValueError("manifest file entry has an unsupported structure")
        digest = record["sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(
            char not in "0123456789abcdefABCDEF" for char in digest
        ):
            raise ValueError("manifest contains an invalid checksum")
        if (
            not isinstance(record["size"], int)
            or isinstance(record["size"], bool)
            or not 0 < record["size"] <= MAX_PRIVATE_FILE_BYTES
        ):
            raise ValueError("manifest contains an invalid file size")
        if not all(
            isinstance(record[key], int)
            and not isinstance(record[key], bool)
            and 0 < record[key] <= 10_000
            for key in ("width", "height")
        ):
            raise ValueError("manifest contains invalid dimensions")
        path = _safe_child(private_dir, private_dir / name, "private asset")
        if not path.is_file():
            raise ValueError("private asset is missing")
        data = _read_limited(path, MAX_PRIVATE_FILE_BYTES)
        if len(data) != record["size"] or hashlib.sha256(data).hexdigest() != digest.lower():
            raise ValueError("private asset does not match its manifest")
        pixels, width, height = _png_pixels(data)
        if width != record["width"] or height != record["height"]:
            raise ValueError("private asset dimensions do not match its manifest")
        assets.append(PrivateAsset(name, data, digest.lower(), pixels, _decode_qr(data)))
    return assets


def _png_pixels(data: bytes) -> tuple[bytes | None, int | None, int | None]:
    """Return canonical RGBA pixels for ordinary non-interlaced PNGs."""
    if not data.startswith(PNG_SIGNATURE):
        return None, None, None
    offset = len(PNG_SIGNATURE)
    width = height = color_type = bit_depth = interlace = None
    compressed = bytearray()
    try:
        while offset + 12 <= len(data):
            length = int.from_bytes(data[offset:offset + 4], "big")
            kind = data[offset + 4:offset + 8]
            body_start = offset + 8
            body_end = body_start + length
            if body_end + 4 > len(data):
                return None, None, None
            body = data[body_start:body_end]
            offset = body_end + 4
            if kind == b"IHDR":
                width = int.from_bytes(body[0:4], "big")
                height = int.from_bytes(body[4:8], "big")
                bit_depth, color_type, _, _, interlace = body[8:13]
            elif kind == b"IDAT":
                compressed.extend(body)
            elif kind == b"IEND":
                break
        if (
            not width or not height or bit_depth != 8 or interlace != 0
            or color_type not in {0, 2, 4, 6}
        ):
            return None, None, None
        channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
        stride = width * channels
        raw = zlib.decompress(bytes(compressed))
        if len(raw) != height * (stride + 1):
            return None, None, None
        previous = bytearray(stride)
        result = bytearray()
        cursor = 0
        for _ in range(height):
            filter_type = raw[cursor]
            cursor += 1
            row = bytearray(raw[cursor:cursor + stride])
            cursor += stride
            _undo_png_filter(row, previous, filter_type, channels)
            for index in range(0, stride, channels):
                pixel = row[index:index + channels]
                if color_type == 0:
                    result.extend((pixel[0], pixel[0], pixel[0], 255))
                elif color_type == 2:
                    result.extend((*pixel, 255))
                elif color_type == 4:
                    result.extend((pixel[0], pixel[0], pixel[0], pixel[1]))
                else:
                    result.extend(pixel)
            previous = row
        return bytes(result), width, height
    except (IndexError, ValueError, zlib.error):
        return None, None, None


def _undo_png_filter(row: bytearray, previous: bytearray, filter_type: int, bpp: int) -> None:
    for index, value in enumerate(row):
        left = row[index - bpp] if index >= bpp else 0
        above = previous[index]
        upper_left = previous[index - bpp] if index >= bpp else 0
        if filter_type == 1:
            row[index] = (value + left) & 255
        elif filter_type == 2:
            row[index] = (value + above) & 255
        elif filter_type == 3:
            row[index] = (value + ((left + above) // 2)) & 255
        elif filter_type == 4:
            pa, pb, pc = abs(above - upper_left), abs(left - upper_left), abs(left + above - 2 * upper_left)
            predictor = left if pa <= pb and pa <= pc else above if pb <= pc else upper_left
            row[index] = (value + predictor) & 255
        elif filter_type != 0:
            raise ValueError("unsupported PNG filter")


def _decode_qr(data: bytes) -> str | None:
    """Optionally compare QR content locally; unavailable decoders are skipped."""
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy  # type: ignore[import-not-found]
    except ImportError:
        return None
    image = cv2.imdecode(numpy.frombuffer(data, dtype=numpy.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    payload, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
    return payload or None


def _tracked_paths(repository: Path) -> Iterable[tuple[str, bytes]]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), "ls-files", "-z"],
            check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("repository must be a readable Git worktree") from exc
    for relative in result.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if not relative:
            continue
        path = repository / relative
        if path.is_file():
            safe_path = _safe_child(repository, path, "repository")
            yield relative, _read_limited(safe_path, MAX_CANDIDATE_FILE_BYTES)


def _directory_paths(directory: Path, label: str) -> Iterable[tuple[str, bytes]]:
    if not directory.is_dir():
        raise ValueError("clone input must be a directory")
    for path in directory.rglob("*"):
        relative = path.relative_to(directory)
        if ".git" in relative.parts:
            continue
        if path.is_file():
            safe_path = _safe_child(directory, path, "clone")
            yield f"{label}/{relative.as_posix()}", _read_limited(safe_path, MAX_CANDIDATE_FILE_BYTES)


def _archive_paths(path: Path) -> Iterable[tuple[str, bytes]]:
    if not path.is_file() or path.stat().st_size > MAX_ARCHIVE_FILE_BYTES:
        raise ValueError("archive exceeds the supported size limit")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                if not item.is_dir() and item.file_size <= MAX_CANDIDATE_FILE_BYTES:
                    if len(item.filename) > MAX_PATH_CHARS:
                        raise ValueError("archive path exceeds the supported limit")
                    yield f"archive:{path.name}/{item.filename}", archive.read(item)
        return
    try:
        with tarfile.open(path) as archive:
            for item in archive:
                if item.isfile() and item.size <= MAX_CANDIDATE_FILE_BYTES:
                    if len(item.name) > MAX_PATH_CHARS:
                        raise ValueError("archive path exceeds the supported limit")
                    handle = archive.extractfile(item)
                    if handle is not None:
                        yield f"archive:{path.name}/{item.name}", handle.read()
    except tarfile.TarError as exc:
        raise ValueError("archive must be a ZIP or TAR file") from exc


def _normal_text(data: bytes) -> str:
    return "".join(chr(byte) for byte in data if byte not in b" \t\r\n\v\f")


def _categories(data: bytes, assets: Iterable[PrivateAsset]) -> set[str]:
    categories: set[str] = set()
    normalized = _normal_text(data)
    pixels, _, _ = _png_pixels(data)
    candidate_qr = _decode_qr(data)
    for asset in assets:
        if asset.data in data:
            categories.add("raw-png")
        digest = asset.sha256
        if digest in normalized.casefold() or bytes.fromhex(digest) in data:
            categories.add("sha256")
        for encoded in (
            base64.b64encode(asset.data).decode("ascii"),
            base64.urlsafe_b64encode(asset.data).decode("ascii").rstrip("="),
        ):
            if encoded in normalized or any(encoded[index:index + 40_000] in normalized for index in range(0, len(encoded), 40_000)):
                categories.add("base64")
        if pixels is not None and pixels == asset.pixels:
            categories.add("decoded-pixels")
        if candidate_qr and asset.qr_payload and candidate_qr == asset.qr_payload:
            categories.add("qr-payload")
    return categories


def check(repository: Path, private_dir: Path, manifest: Path, patches: Iterable[Path], archives: Iterable[Path], clones: Iterable[Path]) -> list[tuple[str, str]]:
    assets = _validate_manifest(private_dir, manifest)
    candidates = list(_tracked_paths(repository))
    for path in patches:
        candidates.append((f"patch:{path.name}", _read_limited(path, MAX_CANDIDATE_FILE_BYTES)))
    for archive in archives:
        candidates.extend(_archive_paths(archive))
    for clone in clones:
        candidates.extend(_directory_paths(clone, f"clone:{clone.name}"))
    if len(candidates) > MAX_FILES:
        raise ValueError("too many candidate files")
    findings: list[tuple[str, str]] = []
    for path, data in candidates:
        for category in sorted(_categories(data, assets)):
            findings.append((path, category))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check public inputs for private donation-asset leakage.")
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--patch", type=Path, action="append", default=[])
    parser.add_argument("--archive", type=Path, action="append", default=[])
    parser.add_argument("--clone", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    try:
        findings = check(args.repository, args.private_dir, args.manifest, args.patch, args.archive, args.clone)
    except ValueError as exc:
        print(f"check failed: {exc}", file=sys.stderr)
        return 2
    for path, category in findings:
        print(f"private donation asset evidence: {category}: {path}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
