from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile

from .models import NoticeGenerationAttempt, NoticeGenerationCache
from .prompts import (
    PROMPT_VERSION,
    build_system_prompt,
    build_user_prompt,
    get_tone_for_target,
)
from .views import _build_cache_key_data


class NoticeGenViewTests(TestCase):
    def _payload(self, **kwargs):
        base = {
            "target": "student_low",
            "topic": "safety",
            "keywords": "물병을 꼭 챙기고 쉬는 시간에는 그늘에서 쉬기",
        }
        base.update(kwargs)
        return base

    def test_guest_daily_limit_is_5(self):
        session = self.client.session
        session.save()
        session_key = session.session_key

        for _ in range(5):
            NoticeGenerationAttempt.objects.create(
                session_key=session_key,
                target="student_low",
                topic="safety",
                tone=get_tone_for_target("student_low"),
                charged=True,
                status=NoticeGenerationAttempt.STATUS_LLM_SUCCESS,
            )

        response = self.client.post(
            reverse("noticegen:generate"),
            self._payload(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "오늘 멘트 생성 횟수(5회)를 모두 사용했습니다.", status_code=429)

    def test_member_daily_limit_is_10(self):
        user = get_user_model().objects.create_user(
            username="teacher",
            password="pw123456",
            email="teacher@example.com",
        )
        profile = UserProfile.objects.get(user=user)
        profile.nickname = "담임"
        profile.save(update_fields=["nickname"])
        self.client.force_login(user)
        for _ in range(10):
            NoticeGenerationAttempt.objects.create(
                user=user,
                target="student_high",
                topic="event",
                tone=get_tone_for_target("student_high"),
                charged=True,
                status=NoticeGenerationAttempt.STATUS_LLM_SUCCESS,
            )

        response = self.client.post(
            reverse("noticegen:generate"),
            self._payload(target="student_high", topic="event"),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "오늘 멘트 생성 횟수(10회)를 모두 사용했습니다.", status_code=429)

    def test_exact_cache_hit_does_not_charge(self):
        payload = self._payload(target="parent", topic="notice", keywords="수학 준비물 챙기기")
        tone = get_tone_for_target(payload["target"])
        key_data = _build_cache_key_data(
            payload["target"],
            payload["topic"],
            tone,
            payload["keywords"],
            [],
        )
        NoticeGenerationCache.objects.create(
            key_hash=key_data["key_hash"],
            prompt_version=PROMPT_VERSION,
            target=payload["target"],
            topic=payload["topic"],
            tone=tone,
            keywords_norm=key_data["keywords_norm"],
            context_norm=key_data["context_norm"],
            signature=key_data["signature"],
            result_text="준비물을 꼭 챙겨주세요.\n내일 수업에서 확인하겠습니다.",
        )

        response = self.client.post(
            reverse("noticegen:generate"),
            payload,
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "저장된 멘트를 불러왔습니다.")
        self.assertEqual(NoticeGenerationAttempt.objects.filter(charged=True).count(), 0)

    @patch("noticegen.views._call_deepseek", side_effect=TimeoutError("timeout"))
    def test_llm_failure_is_charged(self, _mock_call):
        response = self.client.post(
            reverse("noticegen:generate"),
            self._payload(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "멘트 생성 중 오류가 발생했습니다.")
        attempt = NoticeGenerationAttempt.objects.filter(charged=True).latest("id")
        self.assertEqual(attempt.status, NoticeGenerationAttempt.STATUS_LLM_FAIL)

    @patch("noticegen.views._call_deepseek")
    def test_llm_success_creates_cache(self, mock_call):
        mock_call.return_value = (
            "이번 주에는 날씨가 많이 더워요. 물을 자주 마셔요. "
            "쉬는 시간에는 그늘에서 쉬어요."
        )
        response = self.client.post(
            reverse("noticegen:generate"),
            self._payload(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "멘트를 생성했습니다.")
        attempt = NoticeGenerationAttempt.objects.filter(charged=True).latest("id")
        self.assertEqual(attempt.status, NoticeGenerationAttempt.STATUS_LLM_SUCCESS)
        self.assertEqual(NoticeGenerationCache.objects.count(), 1)

    def test_parent_prompt_has_hard_length_and_style_rules(self):
        system_prompt = build_system_prompt("parent")
        user_prompt = build_user_prompt("parent", "notice", "실내화를 챙겨 주세요", "")

        self.assertIn("정확히 3문장", system_prompt)
        self.assertIn("문장 역할 순서", system_prompt)
        self.assertIn("같은 종결어미를 3문장 연속으로 반복하지 않습니다.", system_prompt)
        self.assertIn("공백 포함 90자 이상 140자 이하", system_prompt)
        self.assertIn("공백 포함 90자 이상 140자 이하", user_prompt)

    def test_student_prompt_does_not_include_parent_length_rule(self):
        user_prompt = build_user_prompt("student_low", "notice", "줄넘기 준비", "")
        self.assertNotIn("공백 포함 90자 이상 140자 이하", user_prompt)
