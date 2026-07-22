import unittest

from utils.project_manager import Project


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


if __name__ == "__main__":
    unittest.main()
