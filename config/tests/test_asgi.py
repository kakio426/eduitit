import importlib
import os

from django.test import SimpleTestCase


class AsgiImportOrderTests(SimpleTestCase):
    def test_config_asgi_imports_without_app_registry_error(self):
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings_production"
        module = importlib.import_module("config.asgi")

        self.assertTrue(hasattr(module, "application"))
