from pathlib import Path

from django.test import SimpleTestCase


class DoccollabRuntimeContractTests(SimpleTestCase):
    def test_production_image_installs_node_for_hwpx_generation(self):
        dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"

        self.assertIn("nodejs", dockerfile.read_text(encoding="utf-8"))
