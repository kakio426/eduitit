from pathlib import Path

from django.test import SimpleTestCase


class DoccollabRuntimeContractTests(SimpleTestCase):
    def test_production_image_installs_node_for_hwpx_generation(self):
        dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"

        self.assertIn("nodejs", dockerfile.read_text(encoding="utf-8"))

    def test_frontend_failure_feedback_avoids_blocking_alerts(self):
        root = Path(__file__).resolve().parents[2]
        frontend_paths = [
            root / "doccollab/frontend/src/main.js",
            root / "doccollab/frontend/src/room.js",
            root / "doccollab/static/doccollab/editor/main.js",
            root / "doccollab/static/doccollab/editor/room.js",
        ]

        for path in frontend_paths:
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("window.alert", content)
                self.assertNotIn("response.json()", content)
