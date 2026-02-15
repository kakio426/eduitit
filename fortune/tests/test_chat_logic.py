from datetime import datetime
from django.test import TestCase
from fortune.models import UserSajuProfile
from fortune.utils.chat_logic import build_system_prompt, normalize_natal_chart_payload


class TestChatLogic(TestCase):
    def setUp(self):
        self.profile = UserSajuProfile(
            profile_name="My",
            person_name="TestStudent",
            birth_year=2015,
            birth_month=5,
            birth_day=5,
            birth_hour=12,
            birth_minute=30,
            gender="male",
            calendar_type="solar",
        )

    def test_normalize_chart_supports_multiple_formats(self):
        chart = {
            "year": {"gan": "甲", "ji": "子"},
            "month": ["乙", "丑"],
            "day": "丙寅",
            "hour": {"stem": "丁", "branch": "卯"},
        }
        normalized = normalize_natal_chart_payload(chart)
        self.assertEqual(normalized["year"]["stem"], "甲")
        self.assertEqual(normalized["year"]["branch"], "子")
        self.assertEqual(normalized["month"]["stem"], "乙")
        self.assertEqual(normalized["month"]["branch"], "丑")
        self.assertEqual(normalized["day"]["stem"], "丙")
        self.assertEqual(normalized["day"]["branch"], "寅")
        self.assertEqual(normalized["hour"]["stem"], "丁")
        self.assertEqual(normalized["hour"]["branch"], "卯")

    def test_build_system_prompt_includes_core_context(self):
        natal_chart = {
            "year": {"stem": "甲", "branch": "子"},
            "month": {"stem": "乙", "branch": "丑"},
            "day": {"stem": "丙", "branch": "寅"},
            "hour": {"stem": "丁", "branch": "卯"},
        }
        prompt = build_system_prompt(self.profile, natal_chart, [])
        self.assertIn("Name: TestStudent", prompt)
        self.assertIn("Day Master: 丙", prompt)
        self.assertIn("Birth Datetime: 2015-05-05 12:30", prompt)
        self.assertIn("[Prior General Readings]", prompt)
        self.assertIn('Day Master is fixed as "丙"', prompt)

    def test_build_system_prompt_includes_prior_general_results(self):
        natal_chart = {"day": {"stem": "丙", "branch": "寅"}}
        prior_results = [
            {
                "id": 1,
                "created_at": datetime(2026, 2, 15, 10, 0, 0),
                "result_text": "Strong communication tendency and steady growth in studies.",
            },
            {
                "id": 2,
                "created_at": datetime(2026, 2, 14, 10, 0, 0),
                "result_text": "Focus improves when sleep rhythm is stable.",
            },
        ]
        prompt = build_system_prompt(self.profile, natal_chart, prior_results)
        self.assertIn("Strong communication tendency", prompt)
        self.assertIn("Focus improves when sleep rhythm is stable.", prompt)

class TestChatLogicAliases(TestCase):
    def test_normalize_chart_accepts_time_alias(self):
        chart = {
            "year": {"stem": "A", "branch": "B"},
            "month": {"stem": "C", "branch": "D"},
            "day": {"stem": "E", "branch": "F"},
            "time": {"stem": "G", "branch": "H"},
        }
        normalized = normalize_natal_chart_payload(chart)
        self.assertEqual(normalized["hour"]["stem"], "G")
        self.assertEqual(normalized["hour"]["branch"], "H")
