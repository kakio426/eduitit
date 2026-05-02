import json
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import UserProfile
from fortune.models import Branch, DailyFortuneLog, FortuneResult, Stem

User = get_user_model()


class FortunePrivacyBalancedTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="fortune-user",
            password="password",
            email="fortune@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "운세교사"
        profile.save(update_fields=["nickname"])
        self.assertTrue(self.client.login(username="fortune-user", password="password"))
        self.chart_context = self._build_chart_context()
        self.form_data = {
            "mode": "teacher",
            "gender": "female",
            "birth_year": "1990",
            "birth_month": "5",
            "birth_day": "5",
            "birth_hour": "14",
            "birth_minute": "30",
            "calendar_type": "solar",
        }

    def _build_chart_context(self):
        stems = {
            "甲": Stem.objects.create(name="Gap", character="甲", polarity="yang", element="wood"),
            "乙": Stem.objects.create(name="Eul", character="乙", polarity="yin", element="wood"),
            "丙": Stem.objects.create(name="Byung", character="丙", polarity="yang", element="fire"),
            "丁": Stem.objects.create(name="Jung", character="丁", polarity="yin", element="fire"),
        }
        branches = {
            "子": Branch.objects.create(name="Ja", character="子", polarity="yang", element="water"),
            "丑": Branch.objects.create(name="Chuk", character="丑", polarity="yin", element="earth"),
            "寅": Branch.objects.create(name="In", character="寅", polarity="yang", element="wood"),
            "卯": Branch.objects.create(name="Myo", character="卯", polarity="yin", element="wood"),
        }
        return {
            "year": {"stem": stems["甲"], "branch": branches["子"]},
            "month": {"stem": stems["乙"], "branch": branches["丑"]},
            "day": {"stem": stems["丙"], "branch": branches["寅"]},
            "hour": {"stem": stems["丁"], "branch": branches["卯"]},
        }

    def test_fortune_pages_use_private_meta_and_headers(self):
        saved = FortuneResult.objects.create(
            user=self.user,
            mode="teacher",
            result_text="저장한 사주 결과",
        )

        cases = [
            reverse("fortune:saju"),
            reverse("fortune:history"),
            reverse("fortune:history_detail", kwargs={"pk": saved.pk}),
            reverse("fortune:chat_main"),
        ]

        for path in cases:
            with self.subTest(path=path):
                response = self.client.get(path, follow=True)
                content = response.content.decode("utf-8")

                self.assertEqual(response.status_code, 200)
                self.assertIn('<meta name="robots" content="noindex,nofollow">', content)
                self.assertEqual(response["Cache-Control"], "no-store, private, max-age=0")
                self.assertEqual(response["Pragma"], "no-cache")
                self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_saju_page_removes_name_field_submission_and_auto_save_script(self):
        response = self.client.get(reverse("fortune:saju"), follow=True)
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('name="name"', content)
        self.assertNotIn("autoSaveResult()", content)
        self.assertIn("보관함에 저장", content)

    def test_saju_page_is_guest_accessible_without_login_redirect(self):
        self.client.logout()

        response = self.client.get(reverse("fortune:saju"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [])
        self.assertContains(response, "보관함에 저장")

    def test_saju_api_allows_guest_analysis_without_saving_profile(self):
        self.client.logout()
        ai_mock = AsyncMock(return_value="게스트 사주 분석 결과입니다.")

        with patch("fortune.views._check_saju_ratelimit", new=AsyncMock(return_value=False)), patch(
            "fortune.views.get_chart_context", return_value=self.chart_context
        ), patch("fortune.views.get_prompt", return_value="PROMPT"), patch(
            "fortune.views._collect_ai_response_async", new=ai_mock
        ):
            response = self.client.post(reverse("fortune:saju_api"), self.form_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(FortuneResult.objects.count(), 0)

    def test_saju_api_omits_name_and_does_not_auto_save_result(self):
        ai_mock = AsyncMock(return_value="사주 분석 결과입니다.")

        with patch("fortune.views._check_saju_ratelimit", new=AsyncMock(return_value=False)), patch(
            "fortune.views.get_chart_context", return_value=self.chart_context
        ), patch("fortune.views.get_prompt", return_value="PROMPT"), patch(
            "fortune.views._collect_ai_response_async", new=ai_mock
        ):
            response = self.client.post(reverse("fortune:saju_api"), self.form_data)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("name", response.json())
        self.assertEqual(FortuneResult.objects.count(), 0)

    def test_manual_save_creates_fortune_result(self):
        response = self.client.post(
            reverse("fortune:save_fortune_api"),
            data=json.dumps(
                {
                    "mode": "teacher",
                    "result_text": "생일: 1990년 5월 5일 14시\n요약만 저장합니다.",
                    "target_date": None,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(FortuneResult.objects.filter(user=self.user).count(), 1)

    def test_daily_api_accepts_payload_without_name(self):
        ai_mock = AsyncMock(return_value="오늘의 운세 요약입니다.")

        with patch("fortune.views._check_saju_ratelimit", new=AsyncMock(return_value=False)), patch(
            "fortune.views.calculator.get_pillars", return_value=self.chart_context
        ), patch("fortune.prompts.get_daily_fortune_prompt", return_value="PROMPT") as prompt_mock, patch(
            "fortune.views._collect_ai_response_async", new=ai_mock
        ):
            response = self.client.post(
                reverse("fortune:daily_fortune_api"),
                data=json.dumps(
                    {
                        "target_date": "2026-03-12",
                        "natal_chart": {
                            "year": ["甲", "子"],
                            "month": ["乙", "丑"],
                            "day": ["丙", "寅"],
                            "hour": ["丁", "卯"],
                        },
                        "gender": "female",
                        "mode": "teacher",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["target_date"], "2026-03-12")
        prompt_mock.assert_called_once()
        self.assertEqual(prompt_mock.call_args.args[0], "female")
        self.assertEqual(DailyFortuneLog.objects.filter(user=self.user).count(), 1)

    def test_daily_api_allows_guest_without_saving_log(self):
        self.client.logout()
        ai_mock = AsyncMock(return_value="게스트 오늘 운세입니다.")

        with patch("fortune.views._check_saju_ratelimit", new=AsyncMock(return_value=False)), patch(
            "fortune.views.calculator.get_pillars", return_value=self.chart_context
        ), patch("fortune.prompts.get_daily_fortune_prompt", return_value="PROMPT"), patch(
            "fortune.views._collect_ai_response_async", new=ai_mock
        ):
            response = self.client.post(
                reverse("fortune:daily_fortune_api"),
                data=json.dumps(
                    {
                        "target_date": "2026-03-12",
                        "natal_chart": {
                            "year": ["甲", "子"],
                            "month": ["乙", "丑"],
                            "day": ["丙", "寅"],
                            "hour": ["丁", "卯"],
                        },
                        "gender": "female",
                        "mode": "teacher",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(DailyFortuneLog.objects.count(), 0)
