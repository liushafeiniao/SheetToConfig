"""Small cross-platform integrations with the desktop environment."""

from pathlib import Path

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices


def open_local_path(path: str | Path) -> bool:
    """Ask the desktop environment to open a local file or directory."""
    local_path = Path(path).expanduser().resolve()
    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(local_path))))
