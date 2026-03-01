from unittest.mock import call, patch

from django.test import SimpleTestCase, override_settings

from core.management.commands.bootstrap_runtime import Command


class BootstrapRuntimeCommandTests(SimpleTestCase):
    @override_settings(SHEETBOOK_ROLLOUT_STRICT_STARTUP=False)
    @patch("core.management.commands.bootstrap_runtime.call_command")
    def test_check_sheetbook_rollout_uses_non_strict_by_default(self, mocked_call_command):
        command = Command()

        command._check_sheetbook_rollout()

        mocked_call_command.assert_called_once_with("check_sheetbook_rollout")

    @override_settings(SHEETBOOK_ROLLOUT_STRICT_STARTUP=True)
    @patch("core.management.commands.bootstrap_runtime.call_command")
    def test_check_sheetbook_rollout_uses_strict_when_enabled(self, mocked_call_command):
        command = Command()

        command._check_sheetbook_rollout()

        mocked_call_command.assert_called_once_with("check_sheetbook_rollout", "--strict")

    @override_settings(
        SHEETBOOK_ROLLOUT_STRICT_STARTUP=False,
        SHEETBOOK_ROLLOUT_RECOMMEND_STARTUP=True,
        SHEETBOOK_ROLLOUT_RECOMMEND_DAYS=21,
    )
    @patch("core.management.commands.bootstrap_runtime.call_command")
    def test_check_sheetbook_rollout_runs_recommendation_when_enabled(self, mocked_call_command):
        command = Command()

        command._check_sheetbook_rollout()

        mocked_call_command.assert_has_calls(
            [
                call("check_sheetbook_rollout"),
                call("recommend_sheetbook_thresholds", "--days", "21"),
            ]
        )

    @override_settings(
        SHEETBOOK_ROLLOUT_STRICT_STARTUP=True,
        SHEETBOOK_ROLLOUT_RECOMMEND_STARTUP=True,
        SHEETBOOK_ROLLOUT_RECOMMEND_DAYS=0,
    )
    @patch("core.management.commands.bootstrap_runtime.call_command")
    def test_check_sheetbook_rollout_recommendation_uses_default_days_when_invalid(self, mocked_call_command):
        command = Command()

        command._check_sheetbook_rollout()

        mocked_call_command.assert_has_calls(
            [
                call("check_sheetbook_rollout", "--strict"),
                call("recommend_sheetbook_thresholds", "--days", "14"),
            ]
        )
