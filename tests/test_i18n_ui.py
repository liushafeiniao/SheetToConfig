import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox

from sheet_to_config import i18n
from SheetToConfig import SheetToConfigWindow
from sheet_to_config.dialogs import ProjectEditDialog
from sheet_to_config.utils.project_manager import Project, ProjectManager
from sheet_to_config.utils.export_handler import ExportHandler


ROOT = Path(__file__).resolve().parents[1]


class LocalizedUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.old_locale = i18n._current_locale

    def tearDown(self):
        i18n._current_locale = self.old_locale

    def test_project_required_error_uses_current_locale(self):
        for locale_id in i18n.SUPPORTED_LOCALES:
            with self.subTest(locale=locale_id):
                i18n._current_locale = locale_id
                dialog = ProjectEditDialog()
                with patch("sheet_to_config.dialogs.QMessageBox.warning") as warning:
                    dialog.on_ok()

                warning.assert_called_once_with(
                    dialog,
                    i18n.tr("dialog.input_error"),
                    i18n.tr(
                        "dialog.required_field",
                        field=i18n.tr("dialog.project_name"),
                    ),
                )
                if locale_id != "zh-CN":
                    self.assertNotIn("项目名称", warning.call_args.args[2])
                dialog.close()

    def test_confirmation_translates_title_body_and_buttons(self):
        project_name = "Project 名称 42"
        path = r"D:\tables\原始数据"
        parent = QMainWindow()

        for locale_id in i18n.SUPPORTED_LOCALES:
            with self.subTest(locale=locale_id):
                i18n._current_locale = locale_id
                captured = {}

                def accept_question(box):
                    captured["text"] = box.text()
                    captured["buttons"] = {button.text() for button in box.buttons()}
                    next(
                        button for button in box.buttons()
                        if button.text() == i18n.tr("dialog.yes")
                    ).click()
                    return 0

                with patch.object(QMessageBox, "setWindowTitle") as set_title, patch.object(
                    QMessageBox, "exec_", accept_question
                ):
                    accepted = SheetToConfigWindow._ask_question(
                        parent,
                        "dialog.set_table_dir_title",
                        "dialog.set_table_dir_detail",
                        name=project_name,
                        path=path,
                    )

                self.assertTrue(accepted)
                set_title.assert_called_once_with(
                    i18n.tr("dialog.set_table_dir_title")
                )
                self.assertIn(project_name, captured["text"])
                self.assertIn(path, captured["text"])
                self.assertEqual(
                    {i18n.tr("dialog.yes"), i18n.tr("dialog.no")},
                    captured["buttons"],
                )

        parent.close()

    def test_project_messages_translate_without_translating_user_name(self):
        project_name = "Project 名称 42"
        with tempfile.TemporaryDirectory() as temp_dir:
            projects_file = str(Path(temp_dir) / "projects.json")
            for locale_id in i18n.SUPPORTED_LOCALES:
                with self.subTest(locale=locale_id):
                    i18n._current_locale = locale_id
                    manager = ProjectManager(projects_file)
                    project = Project({
                        "name": project_name,
                        "tablePath": temp_dir,
                        "clientPath": str(Path(temp_dir) / "client"),
                        "serverPath": str(Path(temp_dir) / "server"),
                    })
                    success, message = manager.add_project(project)
                    self.assertTrue(success, message)
                    self.assertEqual(i18n.tr("project.added"), message)

                    duplicate = Project(project.to_dict() | {"id": "duplicate"})
                    success, message = manager.add_project(duplicate)
                    self.assertFalse(success)
                    self.assertEqual(
                        i18n.tr("project.name_exists", name=project_name), message
                    )
                    self.assertIn(project_name, message)

                    Path(projects_file).unlink()

    def test_active_ui_has_no_known_hardcoded_chinese_prompts(self):
        sources = "\n".join(
            (ROOT / name).read_text(encoding="utf-8")
            for name in (
                "sheet_to_config/app.py",
                "sheet_to_config/dialogs.py",
                "sheet_to_config/widgets.py",
                "sheet_to_config/utils/project_manager.py",
                "sheet_to_config/utils/import_handler.py",
                "sheet_to_config/utils/export_handler.py",
            )
        )
        for prompt in (
            '"确认删除"',
            '"请选择项目"',
            '"选择源文件夹"',
            '"选择目标文件夹"',
            '"设置表格目录"',
            "'项目名称'",
            "'无描述'",
        ):
            self.assertNotIn(prompt, sources)

    def test_structured_export_issues_are_localized_by_stable_code(self):
        issue = {
            "code": "REFERENCE_NOT_FOUND",
            "field": "item_id",
            "rawValue": "Project 名称 42",
        }
        for locale_id in i18n.SUPPORTED_LOCALES:
            with self.subTest(locale=locale_id):
                i18n._current_locale = locale_id
                message = ExportHandler._localized_issue_message(issue)
                self.assertEqual(i18n.tr("issue.reference_not_found", field="item_id", value="Project 名称 42", code="REFERENCE_NOT_FOUND"), message)
                self.assertIn("item_id", message)
                self.assertIn("Project 名称 42", message)
                if locale_id in ("en", "es", "ko"):
                    self.assertNotIn("引用", message)

    def test_structured_export_issue_keeps_actionable_core_detail(self):
        issue = {
            "code": "CONVERSION_ERROR",
            "field": "count",
            "rawValue": "oops",
            "message": "A.xlsx/Item!B7 的实际值是 'oops'，请填写整数。",
        }

        message = ExportHandler._localized_issue_message(issue)

        self.assertIn(i18n.tr("issue.conversion_error", field="count"), message)
        self.assertIn("A.xlsx/Item!B7", message)
        self.assertIn("oops", message)
        self.assertIn("请填写整数", message)

    def test_log_levels_use_stable_markers_in_every_locale(self):
        for locale_id in i18n.SUPPORTED_LOCALES:
            with self.subTest(locale=locale_id):
                i18n._current_locale = locale_id
                self.assertEqual(
                    SheetToConfigWindow._log_level(None, "[12:00:00] [ERROR] text"),
                    "error",
                )
                self.assertEqual(
                    SheetToConfigWindow._log_level(None, "[12:00:00] [WARNING] text"),
                    "warning",
                )
                self.assertEqual(
                    SheetToConfigWindow._log_level(None, "[12:00:00] [SUCCESS] text"),
                    "success",
                )

    def test_language_write_failure_is_caught_and_keeps_current_locale(self):
        window = SheetToConfigWindow()
        current = i18n._current_locale
        target = next(item for item in i18n.SUPPORTED_LOCALES if item != current)
        try:
            with patch("sheet_to_config.app.get_locale", return_value=current), patch(
                "sheet_to_config.app.set_locale", side_effect=PermissionError("read-only")
            ), patch("sheet_to_config.app.QMessageBox.warning") as warning:
                window.change_language(target)

            warning.assert_called_once()
            self.assertEqual(i18n._current_locale, current)
        finally:
            window.close()

    def test_window_prevents_a_second_export_while_one_is_running(self):
        class AcceptedDialog:
            def __init__(self, *args, **kwargs):
                pass

            def exec_(self):
                return True

            def get_result(self):
                return "1", "", False, False

        class PendingHandler:
            created = 0

            def __init__(self, *args, **kwargs):
                type(self).created += 1

            def export_async(self, **kwargs):
                return True

        window = SheetToConfigWindow()
        window.current_project = Project({"name": "Demo"})
        window.enable_buttons()
        try:
            with patch("sheet_to_config.app.ExportOptionDialog", AcceptedDialog), patch(
                "sheet_to_config.app.ExportHandlerAsync", PendingHandler
            ):
                window.export_project()
                window.export_project()

            self.assertEqual(PendingHandler.created, 1)
            self.assertTrue(window.export_in_progress)
            self.assertFalse(window.export_btn.isEnabled())
        finally:
            window.on_export_complete(False)
            window.close()


if __name__ == "__main__":
    unittest.main()
