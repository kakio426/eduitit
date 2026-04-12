from unittest.mock import call, patch

from django.test import SimpleTestCase

from core.management.commands.bootstrap_runtime import Command


class BootstrapRuntimeCommandTests(SimpleTestCase):
    @patch.object(Command, "_create_cache_table_if_needed")
    @patch.object(Command, "_run_optional_command")
    @patch("core.management.commands.bootstrap_runtime.call_command")
    def test_handle_runs_ensure_edu_materials(self, mocked_call_command, mocked_optional, mocked_cache):
        command = Command()

        command.handle()

        self.assertIn(call("ensure_edu_materials"), mocked_call_command.call_args_list)
        self.assertIn(call("ensure_tts_announce"), mocked_call_command.call_args_list)

    @patch.object(Command, "_create_cache_table_if_needed")
    @patch.object(Command, "_run_optional_command")
    @patch("core.management.commands.bootstrap_runtime.call_command")
    def test_handle_warms_ocrdesk_without_strict_boot_failure(
        self,
        mocked_call_command,
        mocked_optional,
        mocked_cache,
    ):
        command = Command()

        command.handle()

        self.assertIn(call("warm_ocrdesk"), mocked_optional.call_args_list)
        self.assertNotIn(call("warm_ocrdesk", "--strict"), mocked_optional.call_args_list)
