import json
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import Client, TestCase
from django.urls import reverse

from fortune.models import Branch, DailyFortuneLog, FortunePseudonymousCache, Stem


def _stringify_streaming_response(response):
    async def collect():
        chunks = []
        async for chunk in response.streaming_content:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(chunks)

    return async_to_sync(collect)()


class FortunePublicAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
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
        self.chart_context = self._build_chart_context()
        self.working_context = {
            "display_name": "테스트선생님",
            "gender": "female",
            "mode": "teacher",
            "day_master": {"char": "丙", "element": "fire"},
            "natal_chart": {
                "year": {"stem": "甲", "branch": "子"},
                "month": {"stem": "乙", "branch": "丑"},
                "day": {"stem": "丙", "branch": "寅"},
                "hour": {"stem": "丁", "branch": "卯"},
            },
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

    def test_guest_saju_api_allows_analysis_without_login(self):
        ai_mock = AsyncMock(return_value="사주 분석 결과입니다.")

        with patch("fortune.views._check_saju_ratelimit", new=AsyncMock(return_value=False)), patch(
            "fortune.views.get_chart_context", return_value=self.chart_context
        ), patch("fortune.views.get_prompt", return_value="PROMPT"), patch(
            "fortune.views._collect_ai_response_async", new=ai_mock
        ):
            response = self.client.post(reverse("fortune:saju_api"), self.form_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(FortunePseudonymousCache.objects.count(), 0)

    def test_guest_daily_api_allows_first_request_without_login(self):
        ai_mock = AsyncMock(return_value="오늘의 운세 요약입니다.")

        with patch("fortune.views.check_daily_fortune_limit", new=AsyncMock(return_value=False)), patch(
            "fortune.views.calculator.get_pillars", return_value=self.chart_context
        ), patch("fortune.prompts.get_daily_fortune_prompt", return_value="PROMPT"), patch(
            "fortune.views._collect_ai_response_async", new=ai_mock
        ):
            response = self.client.post(
                reverse("fortune:daily_fortune_api"),
                data=json.dumps(
                    {
                        "target_date": "2026-03-12",
                        "natal_chart": self.working_context["natal_chart"],
                        "gender": "female",
                        "mode": "teacher",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["target_date"], "2026-03-12")
        self.assertEqual(DailyFortuneLog.objects.count(), 0)

    def test_guest_daily_api_returns_limit_after_first_daily_quota(self):
        with patch("fortune.views.check_daily_fortune_limit", new=AsyncMock(return_value=True)):
            response = self.client.post(
                reverse("fortune:daily_fortune_api"),
                data=json.dumps(
                    {
                        "target_date": "2026-03-12",
                        "natal_chart": self.working_context["natal_chart"],
                        "gender": "female",
                        "mode": "teacher",
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["error"], "LIMIT_EXCEEDED")

    @patch("fortune.views_chat.check_chat_limit", new=AsyncMock(return_value=False))
    def test_guest_chat_allows_one_message_then_stops_with_turn_limit_notice(self):
        async def fake_stream(system_prompt, history, user_message):
            self.assertEqual(history, [])
            self.assertEqual(user_message, "안녕하세요")
            yield {"html": "<p>첫 답변</p>", "plain": "첫 답변"}

        with patch("fortune.views_chat.get_ai_response_stream", new=fake_stream):
            first_response = self.client.post(
                reverse("fortune:send_chat_message"),
                {
                    "message": "안녕하세요",
                    "working_context_json": json.dumps(self.working_context, ensure_ascii=False),
                    "history_json": json.dumps([], ensure_ascii=False),
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            first_content = _stringify_streaming_response(first_response)

        second_response = self.client.post(
            reverse("fortune:send_chat_message"),
            {
                "message": "추가 질문",
                "working_context_json": json.dumps(self.working_context, ensure_ascii=False),
                "history_json": json.dumps(
                    [{"role": "user", "content": "안녕하세요"}],
                    ensure_ascii=False,
                ),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertIn("<p>첫 답변</p>", first_content)
        self.assertEqual(second_response.status_code, 200)
        self.assertContains(second_response, "오늘 상담 한도를 모두 사용했습니다")
