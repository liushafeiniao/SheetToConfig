import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from sheet_to_config.dialogs import ExportOptionDialog


class ExportOptionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_regular_export_always_allows_breaking_proto_schema_changes(self):
        dialog = ExportOptionDialog()
        self.addCleanup(dialog.close)

        self.assertFalse(hasattr(dialog, "breaking_proto_checkbox"))
        dialog.select_option("1")

        self.assertEqual(dialog.get_result(), ("1", "", True, False))

    def test_validation_export_always_allows_breaking_proto_schema_changes(self):
        dialog = ExportOptionDialog()
        self.addCleanup(dialog.close)

        self.assertFalse(hasattr(dialog, "breaking_proto_checkbox"))
        dialog.select_option("validate")

        self.assertEqual(dialog.get_result(), ("1", "", True, True))

    def test_specific_export_always_allows_breaking_proto_schema_changes(self):
        dialog = ExportOptionDialog(last_filename="previous")
        self.addCleanup(dialog.close)

        self.assertFalse(hasattr(dialog, "breaking_proto_checkbox"))
        dialog.filename_input.setText("Item")
        dialog.export_specific()

        self.assertEqual(dialog.get_result(), ("4", "Item", True, False))


if __name__ == "__main__":
    unittest.main()
