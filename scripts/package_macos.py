"""Create a distributable macOS DMG around a PyInstaller app bundle."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sheet_to_config.version import __version__


def normalize_arch(machine: str) -> str:
    normalized = machine.casefold()
    if normalized in {"arm64", "aarch64"}:
        return "arm64"
    if normalized in {"x86_64", "amd64"}:
        return "x64"
    raise ValueError(f"Unsupported macOS architecture: {machine}")


def dmg_filename(version: str, arch: str, *, unsigned: bool = False) -> str:
    suffix = "-unsigned" if unsigned else ""
    return f"SheetToConfig-v{version}-macos-{normalize_arch(arch)}{suffix}.dmg"


def create_dmg(app_path: Path, output_path: Path, volume_name: str) -> None:
    if sys.platform != "darwin":
        raise RuntimeError("DMG packaging must run on macOS")
    if not app_path.is_dir() or app_path.suffix != ".app":
        raise ValueError(f"App bundle not found: {app_path}")
    hdiutil = shutil.which("hdiutil")
    if not hdiutil:
        raise RuntimeError("hdiutil is not available")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    with tempfile.TemporaryDirectory(prefix="sheettoconfig-dmg-") as temp_dir:
        root = Path(temp_dir) / "root"
        root.mkdir()
        shutil.copytree(app_path, root / app_path.name, symlinks=True)
        (root / "Applications").symlink_to("/Applications", target_is_directory=True)
        subprocess.run(
            [
                hdiutil,
                "create",
                "-volname",
                volume_name,
                "-srcfolder",
                str(root),
                "-ov",
                "-format",
                "UDZO",
                str(output_path),
            ],
            check=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=ROOT / "dist" / "SheetToConfig.app")
    parser.add_argument("--arch", default=platform.machine())
    parser.add_argument("--version", default=__version__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--unsigned", action="store_true")
    args = parser.parse_args()

    arch = normalize_arch(args.arch)
    output = args.output or ROOT / "dist" / dmg_filename(
        args.version, arch, unsigned=args.unsigned
    )
    create_dmg(args.app.resolve(), output.resolve(), f"SheetToConfig {args.version}")
    print(f"DMG SUCCESS: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
