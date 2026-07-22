"""Inject publisher-supplied donation images into a build checkout.

The public tree deliberately contains no QR images.  This command accepts
private build inputs, verifies both images completely before changing either
target, and uses a recoverable two-file transaction.  It cannot make two
filesystem replacements atomically at the host level.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any

from PyQt5.QtGui import QImage


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "sheet_to_config" / "assets" / "donate"
FILES = {
    "alipay.png": (364, 367),
    "wechat.png": (285, 286),
}
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024
MAX_ENV_CHUNK_CHARS = 40_000
JOURNAL_NAME = ".donation-assets-journal.json"
TRANSACTION_NAME = ".donation-assets-transaction"


class InjectionError(RuntimeError):
    """A deliberately non-sensitive public error."""


def _fail(message: str) -> None:
    raise InjectionError(message)


def _safe_read(path: Path, maximum: int, error: str) -> bytes:
    try:
        with path.open("rb") as handle:
            data = handle.read(maximum + 1)
    except OSError as exc:
        raise InjectionError(error) from exc
    if len(data) > maximum:
        _fail(error)
    return data


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value.lower()
    )


def _png_dimensions(data: bytes) -> tuple[int, int]:
    """Perform structural PNG validation without decoding private content."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        _fail("A donation image is not a valid PNG.")
    position = 8
    seen_ihdr = False
    seen_iend = False
    dimensions: tuple[int, int] | None = None
    while position < len(data):
        if len(data) - position < 12:
            _fail("A donation image is not a valid PNG.")
        length = struct.unpack(">I", data[position : position + 4])[0]
        chunk_end = position + 12 + length
        if chunk_end > len(data):
            _fail("A donation image is not a valid PNG.")
        kind = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        expected_crc = struct.unpack(">I", data[position + 8 + length : chunk_end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
            _fail("A donation image is not a valid PNG.")
        if not seen_ihdr:
            if kind != b"IHDR" or length != 13:
                _fail("A donation image is not a valid PNG.")
            width, height = struct.unpack(">II", payload[:8])
            if not width or not height:
                _fail("A donation image is not a valid PNG.")
            dimensions = (width, height)
            seen_ihdr = True
        elif kind == b"IHDR":
            _fail("A donation image is not a valid PNG.")
        if kind == b"IEND":
            if length != 0 or seen_iend or chunk_end != len(data):
                _fail("A donation image is not a valid PNG.")
            seen_iend = True
            break
        position = chunk_end
    if not seen_ihdr or not seen_iend or dimensions is None:
        _fail("A donation image is not a valid PNG.")
    return dimensions


def _validate_image(data: bytes, expected: dict[str, Any], name: str) -> dict[str, Any]:
    if not data or len(data) > MAX_IMAGE_BYTES:
        _fail("A donation image does not meet the private build requirements.")
    width, height = _png_dimensions(data)
    if len(data) != expected["size"] or _sha256(data) != expected["sha256"]:
        _fail("A donation image does not match its expected integrity metadata.")
    if (width, height) != (expected["width"], expected["height"]):
        _fail("A donation image has unexpected dimensions.")
    image = QImage()
    if not image.loadFromData(data, "PNG") or image.isNull():
        _fail("A donation image cannot be decoded.")
    if (image.width(), image.height()) != (width, height):
        _fail("A donation image has unexpected dimensions.")
    return {"sha256": expected["sha256"], "size": expected["size"]}


def _parse_manifest(path: Path) -> dict[str, dict[str, Any]]:
    raw = _safe_read(path, MAX_MANIFEST_BYTES, "The private manifest cannot be read.")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InjectionError("The private manifest is invalid.") from exc
    if not isinstance(manifest, dict) or set(manifest) != {"version", "files"}:
        _fail("The private manifest is invalid.")
    if manifest["version"] != 1 or not isinstance(manifest["files"], dict):
        _fail("The private manifest is invalid.")
    files = manifest["files"]
    if set(files) != set(FILES):
        _fail("The private manifest is invalid.")
    validated: dict[str, dict[str, Any]] = {}
    for name in FILES:
        entry = files[name]
        if not isinstance(entry, dict) or set(entry) != {"sha256", "size", "width", "height"}:
            _fail("The private manifest is invalid.")
        if (
            not _is_digest(entry["sha256"])
            or not isinstance(entry["size"], int)
            or isinstance(entry["size"], bool)
            or not 0 < entry["size"] <= MAX_IMAGE_BYTES
            or not isinstance(entry["width"], int)
            or not isinstance(entry["height"], int)
            or isinstance(entry["width"], bool)
            or isinstance(entry["height"], bool)
            or not 0 < entry["width"] <= 10000
            or not 0 < entry["height"] <= 10000
        ):
            _fail("The private manifest is invalid.")
        validated[name] = {**entry, "sha256": entry["sha256"].lower()}
    return validated


def _load_from_private_dir(private_dir: Path, manifest_path: Path) -> tuple[dict[str, bytes], dict[str, dict[str, Any]]]:
    public_root = ROOT.resolve()
    for supplied_path in (private_dir, manifest_path):
        lexical_path = supplied_path.absolute()
        resolved_path = supplied_path.resolve()
        for candidate in (lexical_path, resolved_path):
            try:
                candidate.relative_to(public_root)
            except ValueError:
                continue
            _fail("Private donation inputs must remain outside the public repository.")
    metadata = _parse_manifest(manifest_path)
    data = {
        name: _safe_read(private_dir / name, MAX_IMAGE_BYTES, "A private donation image cannot be read.")
        for name in FILES
    }
    return data, metadata


def _load_from_env(environ: dict[str, str]) -> tuple[dict[str, bytes], dict[str, dict[str, Any]]]:
    metadata: dict[str, dict[str, Any]] = {}
    data: dict[str, bytes] = {}
    labels = {"alipay.png": "ALIPAY", "wechat.png": "WECHAT"}
    allowed_environment_names = {
        name
        for label in labels.values()
        for name in (
            f"DONATE_{label}_PNG_B64_1",
            f"DONATE_{label}_PNG_B64_2",
            f"DONATE_{label}_PNG_SHA256",
        )
    }
    supplied_environment_names = {
        name for name in environ if name.startswith("DONATE_")
    }
    if supplied_environment_names != allowed_environment_names:
        _fail("Private donation environment input is incomplete or invalid.")
    for name, label in labels.items():
        prefix = f"DONATE_{label}_PNG_B64_"
        name_prefix = f"DONATE_{label}_PNG_"
        allowed = {prefix + "1", prefix + "2", f"DONATE_{label}_PNG_SHA256"}
        if any(key.startswith(name_prefix) and key not in allowed for key in environ):
            _fail("Private donation environment input is incomplete or invalid.")
        numbered = {key for key in environ if key.startswith(prefix)}
        if numbered != {prefix + "1", prefix + "2"}:
            _fail("Private donation environment input is incomplete or invalid.")
        chunks = [environ[prefix + number] for number in ("1", "2")]
        if any(not chunk or len(chunk) > MAX_ENV_CHUNK_CHARS for chunk in chunks):
            _fail("Private donation environment input is incomplete or invalid.")
        digest_key = f"DONATE_{label}_PNG_SHA256"
        digest = environ.get(digest_key)
        if not _is_digest(digest):
            _fail("Private donation environment input is incomplete or invalid.")
        try:
            decoded = base64.b64decode("".join(chunks), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise InjectionError("Private donation environment input is invalid.") from exc
        width, height = FILES[name]
        data[name] = decoded
        metadata[name] = {"sha256": digest.lower(), "size": len(decoded), "width": width, "height": height}
    return data, metadata


def _validated_payloads(data: dict[str, bytes], metadata: dict[str, dict[str, Any]]) -> dict[str, bytes]:
    if set(data) != set(FILES) or set(metadata) != set(FILES):
        _fail("Private donation input is incomplete.")
    summaries = {name: _validate_image(data[name], metadata[name], name) for name in FILES}
    if data["alipay.png"] == data["wechat.png"]:
        _fail("Private donation images must be distinct.")
    return {name: data[name] for name in summaries}


def _journal_path(asset_dir: Path) -> Path:
    return asset_dir / JOURNAL_NAME


def _transaction_path(asset_dir: Path) -> Path:
    return asset_dir / TRANSACTION_NAME


def _write_json_atomic(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(content, handle, sort_keys=True, separators=(",", ":"))
        temp_name = handle.name
    os.replace(temp_name, path)


def _target_matches(path: Path, expected: dict[str, Any]) -> bool:
    try:
        return path.is_file() and path.stat().st_size == expected["size"] and _sha256(path.read_bytes()) == expected["sha256"]
    except OSError:
        return False


def _read_journal(path: Path) -> dict[str, Any]:
    try:
        journal = json.loads(_safe_read(path, MAX_MANIFEST_BYTES, "Donation recovery metadata is unreadable.").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InjectionError("Donation recovery metadata is invalid.") from exc
    if not isinstance(journal, dict) or set(journal) != {"version", "expected", "prior"} or journal["version"] != 1:
        _fail("Donation recovery metadata is invalid.")
    if set(journal["expected"]) != set(FILES) or set(journal["prior"]) != set(FILES):
        _fail("Donation recovery metadata is invalid.")
    for name in FILES:
        item = journal["expected"][name]
        if not isinstance(item, dict) or set(item) != {"sha256", "size"} or not _is_digest(item["sha256"]) or not isinstance(item["size"], int):
            _fail("Donation recovery metadata is invalid.")
        if not isinstance(journal["prior"][name], bool):
            _fail("Donation recovery metadata is invalid.")
    return journal


def _cleanup_transaction(asset_dir: Path) -> None:
    transaction = _transaction_path(asset_dir)
    if transaction.exists():
        shutil.rmtree(transaction)
    _journal_path(asset_dir).unlink(missing_ok=True)


def _restore_prior(asset_dir: Path, journal: dict[str, Any]) -> None:
    transaction = _transaction_path(asset_dir)
    backup_dir = transaction / "backups"
    restore_dir = transaction / "restore"
    restore_dir.mkdir(exist_ok=True)
    for name in FILES:
        target = asset_dir / name
        backup = backup_dir / name
        if journal["prior"][name]:
            if not backup.is_file():
                _fail("Donation recovery backup is unavailable.")
            staged_restore = restore_dir / name
            shutil.copy2(backup, staged_restore)
            os.replace(staged_restore, target)
        else:
            target.unlink(missing_ok=True)


def recover(asset_dir: Path = ASSET_DIR) -> None:
    """Complete an interrupted transaction, or restore its original pair."""
    journal_file = _journal_path(asset_dir)
    transaction = _transaction_path(asset_dir)
    if not journal_file.exists():
        if transaction.exists():
            _fail("Donation recovery state is incomplete.")
        return
    journal = _read_journal(journal_file)
    if all(_target_matches(asset_dir / name, journal["expected"][name]) for name in FILES):
        _cleanup_transaction(asset_dir)
        return
    _restore_prior(asset_dir, journal)
    _cleanup_transaction(asset_dir)


def _replace_target(source: Path, target: Path) -> None:
    os.replace(source, target)


def inject(payloads: dict[str, bytes], asset_dir: Path = ASSET_DIR) -> None:
    """Write a prevalidated pair using a recoverable transaction."""
    recover(asset_dir)
    asset_dir.mkdir(parents=True, exist_ok=True)
    transaction = _transaction_path(asset_dir)
    transaction.mkdir()
    backups = transaction / "backups"
    staged = transaction / "staged"
    backups.mkdir()
    staged.mkdir()
    try:
        prior = {}
        for name in FILES:
            target = asset_dir / name
            prior[name] = target.is_file()
            if prior[name]:
                shutil.copy2(target, backups / name)
            (staged / name).write_bytes(payloads[name])
        expected = {name: {"sha256": _sha256(payloads[name]), "size": len(payloads[name])} for name in FILES}
        journal = {"version": 1, "expected": expected, "prior": prior}
        _write_json_atomic(_journal_path(asset_dir), journal)
    except OSError as exc:
        shutil.rmtree(transaction, ignore_errors=True)
        raise InjectionError("Donation injection could not prepare its transaction.") from exc
    try:
        for name in FILES:
            _replace_target(staged / name, asset_dir / name)
    except OSError as exc:
        try:
            _restore_prior(asset_dir, journal)
            _cleanup_transaction(asset_dir)
        except OSError as rollback_exc:
            raise InjectionError("Donation injection failed and requires recovery.") from rollback_exc
        raise InjectionError("Donation injection failed; original assets were restored.") from exc
    _cleanup_transaction(asset_dir)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject verified private donation images.")
    parser.add_argument("--private-dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--from-env", action="store_true")
    parser.add_argument("--require", action="store_true")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None, environ: dict[str, str] | None = None) -> int:
    args = parse_args(argv)
    if not args.require:
        _fail("--require is mandatory for donation asset injection.")
    private_mode = args.private_dir is not None or args.manifest is not None
    if args.from_env and private_mode:
        _fail("Choose exactly one private donation input mode.")
    if private_mode:
        if args.private_dir is None or args.manifest is None:
            _fail("--private-dir and --manifest must be provided together.")
        data, metadata = _load_from_private_dir(args.private_dir, args.manifest)
    elif args.from_env:
        data, metadata = _load_from_env(dict(os.environ if environ is None else environ))
    else:
        _fail("Choose exactly one private donation input mode.")
    inject(_validated_payloads(data, metadata))
    return 0


def main() -> int:
    try:
        return run()
    except InjectionError as exc:
        print(f"Donation asset injection failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
