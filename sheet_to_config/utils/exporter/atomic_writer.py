"""Rollback-capable multi-root file commit."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Mapping, Iterable


class AtomicCommitError(RuntimeError):
    pass


def commit_files(writes: Mapping[str | Path, bytes], deletes: Iterable[str | Path]) -> None:
    normalized_writes = {Path(path).resolve(): payload for path, payload in writes.items()}
    normalized_deletes = {Path(path).resolve() for path in deletes}
    overlap = set(normalized_writes) & normalized_deletes
    if overlap:
        raise AtomicCommitError(f"Write/delete target overlap: {next(iter(overlap))}")

    prepared = {}
    backups = {}
    touched = []
    preserved_backups = set()
    try:
        for destination, payload in normalized_writes.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            handle, temp_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
            )
            with os.fdopen(handle, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            prepared[destination] = Path(temp_name)

        for destination in sorted(
            set(normalized_writes) | normalized_deletes, key=lambda item: str(item)
        ):
            if destination.exists():
                handle, backup_name = tempfile.mkstemp(
                    prefix=f".{destination.name}.", suffix=".bak", dir=destination.parent
                )
                os.close(handle)
                shutil.copy2(destination, backup_name)
                backups[destination] = Path(backup_name)
            else:
                backups[destination] = None

        for destination in sorted(normalized_writes, key=lambda item: str(item)):
            os.replace(prepared[destination], destination)
            prepared.pop(destination, None)
            touched.append(destination)
        for destination in sorted(normalized_deletes, key=lambda item: str(item)):
            if destination.exists():
                os.remove(destination)
                touched.append(destination)
    except Exception as exc:
        rollback_errors = []
        for destination in reversed(touched):
            backup = backups.get(destination)
            try:
                if backup and backup.exists():
                    os.replace(backup, destination)
                    backups[destination] = None
                elif destination.exists():
                    os.remove(destination)
            except Exception as rollback_exc:
                rollback_errors.append(f"{destination}: {rollback_exc}")
                if backup and backup.exists():
                    preserved_backups.add(backup)
        if rollback_errors:
            raise AtomicCommitError(
                "Atomic commit failed and rollback was incomplete; backups preserved: "
                + ", ".join(str(path) for path in sorted(preserved_backups))
                + "; "
                + "; ".join(rollback_errors)
            ) from exc
        raise AtomicCommitError(f"Atomic commit failed; old files restored: {exc}") from exc
    finally:
        for path in prepared.values():
            if path.exists():
                path.unlink()
        for path in backups.values():
            if path and path not in preserved_backups and path.exists():
                path.unlink()
