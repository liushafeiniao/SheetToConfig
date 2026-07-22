import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from dialogs import ExportOptionDialog


class ExportOptionDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_validation_only_is_available_and_breaking_proto_is_opt_in(self):
        dialog = ExportOptionDialog()
        self.assertFalse(dialog.breaking_proto_checkbox.isChecked())
        self.assertFalse(dialog.breaking_proto_checkbox.isHidden())
        dialog.breaking_proto_checkbox.setChecked(True)
        dialog.validation_only_checkbox.setChecked(True)
        dialog.select_option("1")

        self.assertEqual(dialog.get_result(), ("1", "", True, True))


if __name__ == "__main__":
    unittest.main()
