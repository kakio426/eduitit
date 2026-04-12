from unittest.mock import patch

from django.test import SimpleTestCase

from core.management.commands.bootstrap_runtime import Command


class SchoolcommIntegrationTests(SimpleTestCase):
    def test_schoolcomm_app_is_enabled_in_production_settings(self):
        from config import settings_production

        self.assertIn("schoolcomm.apps.SchoolcommConfig", settings_production.INSTALLED_APPS)

    def test_bootstrap_runtime_runs_ensure_schoolcomm(self):
        command = Command()
        called_commands = []

        def fake_call_command(name, *args, **kwargs):
            called_commands.append(name)

        with patch("core.management.commands.bootstrap_runtime.call_command", side_effect=fake_call_command):
            with patch.object(Command, "_create_cache_table_if_needed", lambda self: None):
                with patch.object(Command, "_run_optional_command", lambda self, *args: None):
                    command.handle()

        self.assertIn("ensure_schoolcomm", called_commands)
