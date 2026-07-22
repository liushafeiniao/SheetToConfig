"""Structured validation diagnostics shared by CLI-style and GUI callers."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    file: str = ""
    sheet: str = ""
    row: int = 0
    column: int = 0
    field: str = ""
    path: str = ""
    raw_value: Any = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "file": self.file,
            "sheet": self.sheet,
            "row": self.row,
            "column": self.column,
            "field": self.field,
            "path": self.path,
            "rawValue": self.raw_value,
        }
