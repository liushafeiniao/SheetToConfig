import tempfile
import unittest
from pathlib import Path

from utils.project_manager import Project, ProjectManager


class ProjectSettingsTests(unittest.TestCase):
    def test_asset_root_round_trips_and_remains_optional(self):
        project = Project({
            "name": "Game", "tablePath": "tables", "clientPath": "client",
            "serverPath": "server", "assetRoot": "assets",
        })

        self.assertEqual(project.asset_root, "assets")
        self.assertEqual(project.to_dict()["assetRoot"], "assets")
        without_root = Project(project.to_dict() | {"assetRoot": ""})
        self.assertEqual(without_root.asset_root, "")

    def test_search_keeps_persisted_project_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ProjectManager(str(Path(temp_dir) / "projects.json"))
            manager.projects = [
                Project({"id": "a", "name": "A", "sortOrder": 30}),
                Project({"id": "b", "name": "B", "sortOrder": 10}),
                Project({"id": "c", "name": "C", "sortOrder": 20}),
            ]

            self.assertEqual([p.id for p in manager.search_projects("")], ["b", "c", "a"])
            self.assertEqual([p.id for p in manager.search_projects("b")], ["b"])


if __name__ == "__main__":
    unittest.main()
