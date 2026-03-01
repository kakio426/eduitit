from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class CheckCollectSchemaCommandTests(SimpleTestCase):
    @patch("collect.management.commands.check_collect_schema.get_collect_schema_status")
    def test_check_collect_schema_passes_when_ready(self, mocked_status):
        mocked_status.return_value = (True, [], {}, "")
        out = StringIO()

        call_command("check_collect_schema", stdout=out)

        self.assertIn("[collect] schema check passed", out.getvalue())

    @patch("collect.management.commands.check_collect_schema.get_collect_schema_status")
    def test_check_collect_schema_fails_when_missing_columns(self, mocked_status):
        mocked_status.return_value = (
            False,
            [],
            {"collect_collectionrequest": ["bti_integration_source"]},
            "",
        )
        out = StringIO()

        with self.assertRaises(CommandError):
            call_command("check_collect_schema", stdout=out, stderr=out)

        self.assertIn("missing columns", out.getvalue())
