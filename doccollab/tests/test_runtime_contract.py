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

    def test_rhwp_bridge_reflows_justify_paragraphs_after_spacing_edits(self):
        root = Path(__file__).resolve().parents[2]
        source = (
            root
            / "doccollab/vendor/rhwp-studio/src/embed/doccollab-bridge.ts"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "new Set(['justify', 'distribute', 'split'])",
            source,
        )
        self.assertIn("shouldRefreshDescriptorLayoutAfterEdit", source)

        built_assets = sorted(
            (root / "doccollab/static/doccollab/rhwp-studio/assets").glob("index-*.js")
        )
        self.assertTrue(built_assets)
        built_js = "\n".join(path.read_text(encoding="utf-8") for path in built_assets)
        self.assertIn("new Set([`justify`,`distribute`,`split`])", built_js)

    def test_embedded_studio_can_start_a_blank_document(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "doccollab/vendor/rhwp-studio/src/main.ts").read_text(encoding="utf-8")

        self.assertIn("case 'createNewDocument'", source)

        built_assets = sorted(
            (root / "doccollab/static/doccollab/rhwp-studio/assets").glob("index-*.js")
        )
        self.assertTrue(built_assets)
        built_js = "\n".join(path.read_text(encoding="utf-8") for path in built_assets)
        self.assertIn("createNewDocument", built_js)
