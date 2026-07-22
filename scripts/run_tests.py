"""Run unittest discovery and expose actionable GitHub failure annotations."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _escape_command(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


class GithubTextTestResult(unittest.TextTestResult):
    def _annotate(self, label: str, test: unittest.case.TestCase, error) -> None:
        if os.environ.get("GITHUB_ACTIONS") != "true":
            return
        detail = self._exc_info_to_string(error, test)
        title = _escape_command(f"{label}: {test.id()}")
        message = _escape_command(detail[-8000:])
        module = test.__class__.__module__.replace('.', '/')
        path = f"{module}.py" if module.startswith("tests/") else ".github/workflows/tests.yml"
        print(
            f"::error file={path},line=1,title={title}::{message}",
            flush=True,
        )

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._annotate("Test failure", test, err)

    def addError(self, test, err):
        super().addError(test, err)
        self._annotate("Test error", test, err)

    def addSubTest(self, test, subtest, outcome):
        super().addSubTest(test, subtest, outcome)
        if outcome is not None:
            self._annotate("Subtest failure", subtest, outcome)


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"),
        top_level_dir=str(ROOT),
    )
    result = unittest.TextTestRunner(
        verbosity=2,
        resultclass=GithubTextTestResult,
    ).run(suite)
    if os.environ.get("GITHUB_ACTIONS") == "true" and not result.wasSuccessful():
        failed = [test.id() for test, _ in result.failures + result.errors]
        message = _escape_command("; ".join(failed)[-8000:])
        print(
            f"::error file=.github/workflows/tests.yml,line=46,title=Unittest suite failed::{message}",
            flush=True,
        )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
