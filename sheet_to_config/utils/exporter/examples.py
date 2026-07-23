"""Create the comprehensive, single-file TypeDefinition example workbook."""

from pathlib import Path
from tempfile import TemporaryDirectory

from . import atomic_writer
from .template import TypeDefinitionTemplate


EXAMPLE_FILENAMES = ("TypeDefinition.xlsx",)


def _generate_staged_workbooks(tables: Path, locale: str) -> None:
    tables.mkdir(parents=True, exist_ok=True)
    TypeDefinitionTemplate.create_template(str(tables), locale=locale)


def create_example_workbooks(
    output_root: str | Path,
    *,
    locale: str = "zh-CN",
    force: bool = False,
) -> dict[str, Path]:
    """Atomically write the owned TypeDefinition.xlsx below ``output_root/tables``."""
    root = Path(output_root).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise ValueError(f"Output root is not a directory: {root}")
    if root.exists() and any(root.iterdir()) and not force:
        raise FileExistsError(
            f"Output root must be missing or empty; use --force to replace only "
            f"{', '.join(EXAMPLE_FILENAMES)}: {root}"
        )

    tables = root / "tables"
    root_existed = root.exists()
    tables_existed = tables.exists()
    try:
        with TemporaryDirectory(prefix="sheet-to-config-examples-") as temp_dir:
            staged_tables = Path(temp_dir) / "tables"
            _generate_staged_workbooks(staged_tables, locale)
            destinations = {
                tables / name: (staged_tables / name).read_bytes()
                for name in EXAMPLE_FILENAMES
            }
            atomic_writer.commit_files(destinations, [])
    except Exception:
        if not tables_existed and tables.is_dir():
            try:
                tables.rmdir()
            except OSError:
                pass
        if not root_existed and root.is_dir():
            try:
                root.rmdir()
            except OSError:
                pass
        raise

    return {name: tables / name for name in EXAMPLE_FILENAMES}
