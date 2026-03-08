from pathlib import Path
import re

from django.test import SimpleTestCase


class EnsureCommandUnicodeSafetyTests(SimpleTestCase):
    def test_product_ensure_commands_do_not_use_utf16_surrogate_escapes(self):
        command_dir = Path(__file__).resolve().parents[1] / "management" / "commands"
        surrogate_escape_pattern = re.compile(r"\\u[dD][89A-Fa-f][0-9A-Fa-f]{2}")

        offenders = []
        for path in command_dir.glob("ensure_*.py"):
            content = path.read_text(encoding="utf-8")
            if surrogate_escape_pattern.search(content):
                offenders.append(path.name)

        self.assertEqual(
            offenders,
            [],
            "Use actual emoji or \\U escapes instead of UTF-16 surrogate \\u escapes: "
            + ", ".join(offenders),
        )
