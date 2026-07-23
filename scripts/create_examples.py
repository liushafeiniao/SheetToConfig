"""Generate TypeDefinition.xlsx with embedded localized teaching sheets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sheet_to_config.utils.exporter.examples import create_example_workbooks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Missing or empty output root; TypeDefinition.xlsx is written below tables/.",
    )
    parser.add_argument(
        "--locale",
        default="zh-CN",
        choices=("en", "zh-CN", "ja", "ko", "es", "zh-TW"),
        help="Language used by TypeDefinition.xlsx.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace only TypeDefinition.xlsx.",
    )
    args = parser.parse_args(argv)
    written = create_example_workbooks(
        args.output_dir,
        locale=args.locale,
        force=args.force,
    )
    for name, path in written.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
