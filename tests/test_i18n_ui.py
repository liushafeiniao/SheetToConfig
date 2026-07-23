import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QProgressBar

from sheet_to_config import i18n
from SheetToConfig import SheetToConfigWindow
from sheet_to_config.dialogs import AboutDialog, ProjectEditDialog
from sheet_to_config.utils.updater import ReleaseInfo
from sheet_to_config.utils.project_manager import Project, ProjectManager
from sheet_to_config.utils.export_handler import ExportHandler
from sheet_to_config.utils.issue_messages import ISSUE_ADVICE_KEYS
from sheet_to_config.version import __version__


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
            "path": "Arena.xlsx/Units!B7",
        }
        for locale_id in i18n.SUPPORTED_LOCALES:
            with self.subTest(locale=locale_id):
                i18n._current_locale = locale_id
                message = ExportHandler._localized_issue_message(issue)
                self.assertIn(
                    i18n.tr(
                        "issue.reference_not_found",
                        field="item_id",
                        value="Project 名称 42",
                        code="REFERENCE_NOT_FOUND",
                    ),
                    message,
                )
                self.assertIn("item_id", message)
                self.assertIn("Project 名称 42", message)
                self.assertIn("Arena.xlsx/Units!B7", message)
                if locale_id in ("en", "es", "ko"):
                    self.assertNotIn("引用", message)

    def test_type_definition_issue_is_actionable_in_every_locale(self):
        issue = {
            "code": "TYPE_DEFINITION_PARENTHESIS",
            "field": "missionList",
            "rawValue": "split_list(find_id(mission,突破任务,id)）",
            "path": "TypeDefinition.xlsx/CODE!B37",
        }

        for locale_id in i18n.SUPPORTED_LOCALES:
            with self.subTest(locale=locale_id):
                i18n._current_locale = locale_id
                message = ExportHandler._localized_issue_message(issue)
                self.assertIn("missionList", message)
                self.assertIn("split_list", message)
                self.assertIn("TypeDefinition.xlsx/CODE!B37", message)
                if locale_id != "zh-CN":
                    self.assertNotIn("括号不匹配", message)

    def test_every_structured_issue_has_a_localized_fix_hint(self):
        for locale_id in i18n.SUPPORTED_LOCALES:
            with self.subTest(locale=locale_id):
                i18n._current_locale = locale_id
                for code, advice_key in ISSUE_ADVICE_KEYS.items():
                    with self.subTest(code=code):
                        message = ExportHandler._localized_issue_message({
                            "code": code,
                            "field": "field",
                            "rawValue": "value",
                            "path": "Workbook.xlsx/Sheet!B5",
                        })
                        self.assertIn(i18n.tr(advice_key), message)

    def test_unknown_issue_does_not_echo_raw_locale_specific_detail(self):
        i18n._current_locale = "en"
        message = ExportHandler._localized_issue_message({
            "code": "NEW_INTERNAL_CODE",
            "message": "中文底层异常，不应直接显示",
            "path": "Workbook.xlsx/Sheet!A1",
        })

        self.assertNotIn("中文底层异常", message)
        self.assertIn("Workbook.xlsx/Sheet!A1", message)
        self.assertIn(i18n.tr("issue.advice.generic"), message)

    def test_reference_table_issue_identifies_the_target(self):
        i18n._current_locale = "zh-CN"
        message = ExportHandler._localized_issue_message({
            "code": "REFERENCE_TABLE_ERROR",
            "field": "Missing.xlsx",
            "path": "Source.xlsx/References",
        })

        self.assertIn("Missing.xlsx", message)
        self.assertIn(i18n.tr("issue.advice.reference_table_error"), message)

    def test_structured_export_issue_keeps_actionable_core_detail(self):
        issue = {
            "code": "CONVERSION_ERROR",
            "field": "count",
            "rawValue": "oops",
            "file": "A.xlsx",
            "sheet": "Item",
            "row": 7,
            "column": 2,
        }

        message = ExportHandler._localized_issue_message(issue)

        self.assertIn(i18n.tr("issue.conversion_error", field="count"), message)
        self.assertIn("A.xlsx/Item!B7", message)
        self.assertIn("oops", message)
        self.assertNotIn("请填写整数", message)

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

    def test_update_starts_download_without_confirmation_and_shows_progress(self):
        dialog = AboutDialog()
        release = ReleaseInfo(
            version="9.9.9",
            tag_name="v9.9.9",
            release_url="https://example.com/release",
            asset_name="SheetToConfig-v9.9.9-windows-x64.exe",
            asset_url="https://example.com/update.exe",
            checksum_url="https://example.com/SHA256SUMS.txt",
        )
        try:
            progress_bars = dialog.findChildren(QProgressBar)
            self.assertEqual(1, len(progress_bars))
            self.assertTrue(progress_bars[0].isHidden())

            with patch(
                "sheet_to_config.dialogs.supports_automatic_update",
                return_value=True,
            ), patch.object(QMessageBox, "question") as question:
                dialog._on_update_task_finished({
                    "action": "check",
                    "result": release,
                    "error": None,
                })

            question.assert_not_called()
            self.assertIs(dialog._pending_update_release, release)
            self.assertFalse(progress_bars[0].isHidden())
            self.assertEqual(0, progress_bars[0].value())
        finally:
            dialog.close()

    def test_update_without_new_release_reports_current_version(self):
        dialog = AboutDialog()
        try:
            with patch.object(QMessageBox, "information") as information:
                dialog._on_update_task_finished({
                    "action": "check",
                    "result": None,
                    "error": None,
                })

            information.assert_called_once_with(
                dialog,
                i18n.tr("about.title"),
                i18n.tr("about.update_up_to_date", version=__version__),
            )
        finally:
            dialog.close()

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
            export_calls = []

            def __init__(self, *args, **kwargs):
                type(self).created += 1

            def export_async(self, **kwargs):
                type(self).export_calls.append(kwargs)
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
            self.assertEqual(PendingHandler.export_calls[0]["allow_breaking_proto_change"], True)
            self.assertTrue(window.export_in_progress)
            self.assertFalse(window.export_btn.isEnabled())
        finally:
            window.on_export_complete(False)
            window.close()

    def test_export_handler_normalizes_optional_asset_root(self):
        class CapturingConverter:
            def __init__(self):
                self.calls = []

            def export_all(self, **kwargs):
                self.calls.append(kwargs)
                return {
                    "success": True,
                    "count": 0,
                    "success_count": 0,
                    "fail_count": 0,
                    "issues": [],
                    "changes": {},
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            for configured, expected in (
                ("", ""),
                ("   ", ""),
                ("  C:/game/assets  ", "C:/game/assets"),
            ):
                with self.subTest(asset_root=configured):
                    project = Project({
                        "name": "Demo",
                        "tablePath": temp_dir,
                        "clientPath": "client",
                        "serverPath": "server",
                        "assetRoot": configured,
                    })
                    handler = ExportHandler(project)
                    converter = CapturingConverter()
                    handler.converter = converter

                    self.assertTrue(handler.export(validation_only=True))
                    self.assertEqual(
                        converter.calls[0]["asset_root"], expected
                    )

    def test_export_handler_does_not_repeat_aggregate_artifact_changes(self):
        class ConverterWithPerFileLog:
            def __init__(self, relay):
                self.relay = relay

            def export_all(self, **kwargs):
                self.relay("英雄.xlsx\n  [OK] Hero.pb")
                return {
                    "success": True,
                    "count": 1,
                    "success_count": 1,
                    "fail_count": 0,
                    "issues": [],
                    "changes": {
                        "client": {
                            "added": ["Attribute.pb", "Hero.pb"],
                            "modified": ["Skill.pb"],
                            "removed": ["Legacy.pb"],
                        },
                        "server": {
                            "added": ["ServerAdded.pb"],
                            "modified": ["ServerModified.pb"],
                            "removed": ["ServerRemoved.pb"],
                        }
                    },
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Project({
                "name": "Demo",
                "tablePath": temp_dir,
                "clientPath": "client",
                "serverPath": "server",
            })
            logs = []
            handler = ExportHandler(project, logs.append)
            handler.converter = ConverterWithPerFileLog(
                handler._relay_converter_log
            )

            self.assertTrue(handler.export())

        self.assertIn("英雄.xlsx\n  [OK] Hero.pb", logs)
        for aggregate_only_path in (
            "Attribute.pb", "Skill.pb", "Legacy.pb", "ServerAdded.pb",
            "ServerModified.pb", "ServerRemoved.pb",
        ):
            with self.subTest(path=aggregate_only_path):
                self.assertFalse(
                    any(aggregate_only_path in line for line in logs), logs
                )
        self.assertEqual(
            handler.last_result["changes"]["client"]["added"],
            ["Attribute.pb", "Hero.pb"],
        )


if __name__ == "__main__":
    unittest.main()
