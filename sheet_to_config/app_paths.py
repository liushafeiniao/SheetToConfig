"""Resolve writable application data without coupling it to the source tree."""

import os
import shutil
import sys
import tempfile
from pathlib import Path


DATA_DIR_ENV = "SHEETTOCONFIG_DATA_DIR"
LEGACY_DATA_DIR_ENVS = ("GAMETABLEFORGE_DATA_DIR",)
LEGACY_DATA_DIR_NAMES = ("GameTableForgeData", "TableManagerData", "GameTableForge", "TableManager")
LEGACY_CACHE_NAMES = ("GameTableForge_bg_cache.png", "TableManager_bg_cache.png")

_migration_key: tuple[str, tuple[str, ...], str] | None = None


def _user_data_dir() -> Path:
    """Return a stable per-user source-mode data directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SheetToConfig"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata).expanduser() if appdata else Path.home() / "AppData" / "Roaming"
        return base / "SheetToConfig"
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home).expanduser() / "SheetToConfig"
    return Path.home() / ".config" / "SheetToConfig"


def _canonical_data_dir() -> Path:
    """Resolve the directory used by the current product without migration."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()

    if getattr(sys, "frozen", False):
        return (
            Path(sys.executable).resolve().parent
            if sys.platform == "win32" else _user_data_dir()
        )

    source_dir = Path(__file__).resolve().parent.parent
    sibling_data_dir = source_dir.parent / "LocalData"
    if sibling_data_dir.is_dir():
        return sibling_data_dir
    return _user_data_dir()


def legacy_data_dirs() -> list[Path]:
    """Return plausible pre-SheetToConfig state locations, oldest first."""
    candidates: list[Path] = []
    for env_name in LEGACY_DATA_DIR_ENVS:
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value).expanduser().resolve())

    source_dir = Path(__file__).resolve().parent.parent
    parent = source_dir.parent
    candidates.extend(parent / name for name in LEGACY_DATA_DIR_NAMES)
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.extend(Path(appdata) / name for name in ("GameTableForge", "TableManager"))

    result: list[Path] = []
    seen: set[Path] = set()
    canonical = _canonical_data_dir()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate == canonical or candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_dir():
            result.append(candidate)
    return result


def migrate_legacy_data(target: Path | str | None = None,
                        legacy_dirs: list[Path | str] | None = None) -> list[Path]:
    """Copy old local state into the new directory without overwriting it.

    Copying rather than deleting the source makes the migration recoverable and
    allows an interrupted startup to be retried safely.
    """
    destination = Path(target).expanduser().resolve() if target else _canonical_data_dir()
    sources = [Path(path).expanduser().resolve() for path in legacy_dirs] if legacy_dirs is not None else legacy_data_dirs()
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source in sources:
        if not source.is_dir() or source == destination:
            continue
        for item in source.iterdir():
            target_path = destination / item.name
            if target_path.exists():
                continue
            try:
                if item.is_file():
                    shutil.copy2(item, target_path)
                    copied.append(target_path)
                elif item.is_dir() and item.name not in {"__pycache__"}:
                    shutil.copytree(item, target_path)
                    copied.append(target_path)
            except (OSError, shutil.Error):
                # A single locked or malformed legacy item must not prevent
                # the application from starting with the remaining state.
                continue
    return copied


def migrate_legacy_cache(target: Path | str | None = None) -> Path | None:
    """Copy the old temporary background cache to the canonical filename."""
    # Preserve an explicitly supplied path's spelling. On Windows, resolve()
    # can expand an 8.3 path (ADMINI~1) to its long form, which makes callers
    # receive a different Path even though it points to the same file.
    temp_dir = Path(target or tempfile.gettempdir()).expanduser()
    new_path = temp_dir / "SheetToConfig_bg_cache.png"
    if new_path.exists():
        return new_path
    for old_name in LEGACY_CACHE_NAMES:
        old_path = temp_dir / old_name
        if old_path.is_file():
            try:
                shutil.copy2(old_path, new_path)
                return new_path
            except OSError:
                return None
    return None


def local_data_dir() -> Path:
    """Return the directory used for local, untracked application state."""
    global _migration_key
    target = _canonical_data_dir()
    key = (
        str(target),
        tuple(os.environ.get(name, "") for name in LEGACY_DATA_DIR_ENVS),
        tempfile.gettempdir(),
    )
    if key != _migration_key:
        _migration_key = key
        migrate_legacy_data(target)
        migrate_legacy_cache()
    return target


def local_data_path(filename: str) -> Path:
    """Resolve one local state file and reject paths outside the data directory."""
    relative = Path(filename)
    if relative.is_absolute() or len(relative.parts) != 1 or filename in {"", ".", ".."}:
        raise ValueError("filename must be a single relative path component")
    return local_data_dir() / relative
