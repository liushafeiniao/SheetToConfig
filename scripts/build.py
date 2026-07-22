# -*- coding: utf-8 -*-
"""Build a native SheetToConfig application with the canonical spec."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
WORK_DIR = Path(tempfile.gettempdir()) / "SheetToConfig-pyinstaller-build"
DIST_DIR = BASE_DIR / "dist"
STAGE_DIR = DIST_DIR / ".staging"
SPEC_FILE = BASE_DIR / "packaging" / "SheetToConfig.spec"


def artifact_name(platform_name: str | None = None) -> str:
    """Return the platform-native artifact produced by PyInstaller."""
    target_platform = platform_name or sys.platform
    if target_platform == "win32":
        return "SheetToConfig.exe"
    if target_platform == "darwin":
        return "SheetToConfig.app"
    return "SheetToConfig"


def exe_is_running(target: Path) -> bool:
    """Return whether Windows is locking this checkout's packaged executable."""
    if sys.platform != "win32":
        return False

    target_path = str(target.resolve()).casefold()
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Process -Filter "
                "\"Name = 'SheetToConfig.exe'\").ExecutablePath",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        running_paths = {
            line.strip().casefold()
            for line in out.stdout.splitlines()
            if line.strip()
        }
        return target_path in running_paths
    except OSError:
        try:
            out = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq SheetToConfig.exe", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            return "SheetToConfig.exe" in out.stdout
        except OSError:
            return False


def check_dependencies() -> bool:
    """Check build dependencies without mutating the Python environment."""
    try:
        import PyInstaller  # noqa: F401
        import PyQt5  # noqa: F401
        import google.protobuf  # noqa: F401
        import openpyxl  # noqa: F401
    except ImportError as exc:
        print(f"ERROR: Missing build dependency: {exc}")
        print("Run: python -m pip install -r requirements-dev.txt")
        return False
    return True


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def replace_artifact(staged: Path, output: Path) -> None:
    """Replace a file or app bundle while preserving the old output on error."""
    backup = output.with_name(f".{output.name}.backup")
    _remove_path(backup)
    had_previous = output.exists()
    if had_previous:
        os.replace(output, backup)
    try:
        os.replace(staged, output)
    except OSError:
        if had_previous and backup.exists():
            os.replace(backup, output)
        raise
    _remove_path(backup)


def build_application() -> bool:
    """Build the platform-native application into dist/."""
    target = DIST_DIR / artifact_name()
    if target.exists() and exe_is_running(target):
        print("ERROR: SheetToConfig.exe 正在运行，打包后无法替换它。")
        print("请先关闭 SheetToConfig，再重新运行本脚本。")
        return False

    if not check_dependencies():
        return False

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath",
        str(WORK_DIR),
        "--distpath",
        str(STAGE_DIR),
        str(SPEC_FILE),
    ]
    print("Build command:", " ".join(command))

    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)

    try:
        result = subprocess.run(command, cwd=BASE_DIR, check=False)
        staged_output = STAGE_DIR / artifact_name()
        if result.returncode != 0 or not staged_output.exists():
            print("Build FAILED; the previous application was preserved.")
            return False

        DIST_DIR.mkdir(parents=True, exist_ok=True)
        replace_artifact(staged_output, target)
        print(f"Build SUCCESS: {target}")
        return True
    except OSError as exc:
        print(f"Build FAILED while replacing the application: {exc}")
        return False
    finally:
        if WORK_DIR.exists():
            shutil.rmtree(WORK_DIR)
        if STAGE_DIR.exists():
            shutil.rmtree(STAGE_DIR)


def main() -> int:
    print("=" * 50)
    print("SheetToConfig Build")
    print("=" * 50)
    return 0 if build_application() else 1


if __name__ == "__main__":
    raise SystemExit(main())
