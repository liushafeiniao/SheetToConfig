import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class HeadlessExporterTests(unittest.TestCase):
    def test_exporter_import_does_not_require_pyqt5(self):
        script = f"""
import builtins
import sys
sys.path.insert(0, {str(ROOT)!r})
real_import = builtins.__import__
def blocked_import(name, *args, **kwargs):
    if name == 'PyQt5' or name.startswith('PyQt5.'):
        raise ModuleNotFoundError('PyQt5 blocked by test')
    return real_import(name, *args, **kwargs)
builtins.__import__ = blocked_import
from utils.exporter import ExcelConverter
print(ExcelConverter.__name__)
"""

        completed = subprocess.run(
            [sys.executable, "-I", "-c", script],
            capture_output=True, text=True, check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "ExcelConverter")


if __name__ == "__main__":
    unittest.main()
