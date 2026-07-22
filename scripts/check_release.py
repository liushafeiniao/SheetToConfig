"""Validate that a release tag matches the source version and changelog."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
VERSION_ASSIGNMENT_RE = re.compile(
    r'^__version__\s*=\s*["\']([^"\']+)["\']\s*$', re.MULTILINE
)


def read_source_version(path: Path) -> str:
    match = VERSION_ASSIGNMENT_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError(f"No __version__ assignment found in {path}")
    return match.group(1)


def validate_release(tag: str, version_path: Path, changelog_path: Path) -> str:
    version = read_source_version(version_path)
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(f"version file contains an invalid SemVer: {version}")
    expected_tag = f"v{version}"
    if tag != expected_tag:
        raise ValueError(f"Release tag {tag!r} must exactly match {expected_tag!r}")
    changelog = changelog_path.read_text(encoding="utf-8")
    heading = re.compile(
        rf"^##\s+\[{re.escape(version)}\](?:\s+-\s+\d{{4}}-\d{{2}}-\d{{2}})?\s*$",
        re.MULTILINE,
    )
    if not heading.search(changelog):
        raise ValueError(f"CHANGELOG.md has no release heading for {version}")
    return version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=os.environ.get("GITHUB_REF_NAME", ""))
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument(
        "--version-file", type=Path, default=ROOT / "sheet_to_config" / "version.py"
    )
    parser.add_argument("--changelog", type=Path, default=ROOT / "CHANGELOG.md")
    args = parser.parse_args()
    if args.self_check:
        args.tag = f"v{read_source_version(args.version_file)}"
    elif not args.tag:
        parser.error("--tag or GITHUB_REF_NAME is required")
    version = validate_release(args.tag, args.version_file, args.changelog)
    print(f"Release metadata valid: tag={args.tag} version={version}")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"version={version}\n")
            output.write(f"tag=v{version}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
