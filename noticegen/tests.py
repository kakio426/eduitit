from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile

from .models import NoticeGenerationAttempt, NoticeGenerationCache
from .prompts import (
    LENGTH_LONG,
    LENGTH_SHORT,
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
        self.assertContains(response, "준비물을 꼭 챙겨주세요.")
        self.assertNotContains(response, "저장된 멘트를 불러왔습니다.")
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
        self.assertContains(response, "이번 주에는 날씨가 많이 더워요.")
        self.assertNotContains(response, "멘트를 생성했습니다.")
        attempt = NoticeGenerationAttempt.objects.filter(charged=True).latest("id")
        self.assertEqual(attempt.status, NoticeGenerationAttempt.STATUS_LLM_SUCCESS)
        self.assertEqual(NoticeGenerationCache.objects.count(), 1)

    @patch("noticegen.views._call_deepseek")
    def test_similar_cache_does_not_reuse_different_safety_instruction(self, mock_call):
        payload = self._payload(
            target="student_high",
            topic="safety",
            keywords="전동 퀵보드 탑승 금지",
        )
        tone = get_tone_for_target(payload["target"])
        cached_key = _build_cache_key_data(
            payload["target"],
            payload["topic"],
            tone,
            "전동퀵보드 이용 시 안전모 착용",
            [],
        )
        NoticeGenerationCache.objects.create(
            key_hash=cached_key["key_hash"],
            prompt_version=PROMPT_VERSION,
            target=payload["target"],
            topic=payload["topic"],
            tone=tone,
            keywords_norm=cached_key["keywords_norm"],
            context_norm=cached_key["context_norm"],
            signature=cached_key["signature"],
            result_text="전동퀵보드를 이용할 때는 안전모를 착용해야 합니다.",
        )
        mock_call.return_value = "전동 퀵보드는 안전을 위해 탑승하지 않습니다. 발견하면 바로 내려 주세요."

        response = self.client.post(
            reverse("noticegen:generate"),
            payload,
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "전동 퀵보드는 안전을 위해 탑승하지 않습니다.")
        self.assertNotContains(response, "안전모를 착용해야 합니다.")
        attempt = NoticeGenerationAttempt.objects.filter(charged=True).latest("id")
        self.assertEqual(attempt.status, NoticeGenerationAttempt.STATUS_LLM_SUCCESS)

    def test_near_duplicate_keywords_reuse_cache_without_reuse_banner(self):
        payload = self._payload(
            target="parent",
            topic="notice",
            keywords="체험학습 준비물 안내.",
        )
        tone = get_tone_for_target(payload["target"])
        cached_key = _build_cache_key_data(
            payload["target"],
            payload["topic"],
            tone,
            "체험학습 준비물 안내",
            [],
        )
        NoticeGenerationCache.objects.create(
            key_hash=cached_key["key_hash"],
            prompt_version=PROMPT_VERSION,
            target=payload["target"],
            topic=payload["topic"],
            tone=tone,
            keywords_norm=cached_key["keywords_norm"],
            context_norm=cached_key["context_norm"],
            signature=cached_key["signature"],
            result_text="체험학습 준비물을 전날 다시 확인해 주시고, 물통과 필기도구를 챙겨 보내 주세요.",
        )

        response = self.client.post(
            reverse("noticegen:generate"),
            payload,
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "체험학습 준비물을 전날 다시 확인해 주시고")
        self.assertNotContains(response, "재사용했습니다")
        self.assertEqual(NoticeGenerationAttempt.objects.filter(charged=True).count(), 0)

    @patch("noticegen.views._call_deepseek")
    def test_generate_mini_success_renders_compact_success_panel(self, mock_call):
        mock_call.return_value = "준비물을 꼭 챙기고 안전하게 이동합니다."

        response = self.client.post(
            reverse("noticegen:generate_mini"),
            self._payload(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-mini-app-state="success"', html=False)
        self.assertContains(response, "결과 미리보기")
        self.assertContains(response, 'data-mini-app-action="copy"', html=False)
        self.assertContains(response, "준비물을 꼭 챙기고 안전하게 이동합니다.")

    def test_generate_mini_validation_error_renders_error_state(self):
        response = self.client.post(
            reverse("noticegen:generate_mini"),
            self._payload(keywords=""),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'data-mini-app-state="error"', status_code=400, html=False)
        self.assertContains(response, "전달 사항을 2글자 이상 적어 주세요.", status_code=400)

    def test_generate_mini_daily_limit_uses_compact_error_panel(self):
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
            reverse("noticegen:generate_mini"),
            self._payload(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'data-mini-app-state="error"', status_code=429, html=False)
        self.assertContains(response, "오늘 멘트 생성 횟수(5회)를 모두 사용했습니다.", status_code=429)

    def test_parent_prompt_has_length_and_natural_flow_rules(self):
        system_prompt = build_system_prompt("parent", LENGTH_LONG)
        user_prompt = build_user_prompt("parent", "notice", "실내화를 챙겨 주세요", "", LENGTH_LONG)

        self.assertIn("분량 규칙", system_prompt)
        self.assertIn("선택 분량: 길게", system_prompt)
        self.assertIn("문장은 한 단락처럼 읽히도록 자연스럽게 연결", system_prompt)
        self.assertNotIn("정확히 3문장", system_prompt)
        self.assertIn("문어체", system_prompt)
        self.assertIn("거예요", system_prompt)
        self.assertIn("않을 거야", system_prompt)
        self.assertIn("분량: 길게", user_prompt)
        self.assertIn("공백 포함 180~260자", user_prompt)
        self.assertIn("문어체 공지문", user_prompt)

    def test_student_prompt_does_not_include_parent_only_guidance(self):
        user_prompt = build_user_prompt("student_low", "notice", "줄넘기 준비", "", LENGTH_SHORT)
        self.assertIn("분량: 짧게", user_prompt)
        self.assertNotIn("협조 요청 표현은 명령형보다 완곡한 안내형", user_prompt)

    def test_student_prompts_enforce_written_style(self):
        low_system_prompt = build_system_prompt("student_low")
        high_system_prompt = build_system_prompt("student_high")
        low_user_prompt = build_user_prompt("student_low", "notice", "실내화와 물통 준비", "")
        high_user_prompt = build_user_prompt("student_high", "notice", "실내화와 물통 준비", "")

        for prompt_text in (low_system_prompt, high_system_prompt):
            self.assertIn("문어체", prompt_text)
            self.assertIn("거예요", prompt_text)
            self.assertIn("않을 거야", prompt_text)

        for prompt_text in (low_user_prompt, high_user_prompt):
            self.assertIn("구어체", prompt_text)
            self.assertIn("문어체 공지문", prompt_text)

    def test_cache_key_changes_when_length_style_changes(self):
        base = _build_cache_key_data(
            "parent",
            "notice",
            get_tone_for_target("parent"),
            "준비물을 챙겨 주세요",
            [],
            "medium",
        )
        short = _build_cache_key_data(
            "parent",
            "notice",
            get_tone_for_target("parent"),
            "준비물을 챙겨 주세요",
            [],
            LENGTH_SHORT,
        )

        self.assertNotEqual(base["key_hash"], short["key_hash"])

    def test_main_uses_teacher_first_sections(self):
        response = self.client.get(reverse("noticegen:main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "바로 쓰는 안내문 문장")
        self.assertContains(response, "그냥 적어 주세요")
        self.assertContains(response, "직접 조정")
        self.assertContains(response, "생성 결과")
        self.assertContains(response, "문장 만들기")
        self.assertEqual(response.context["initial_target"], "parent")
        self.assertEqual(response.context["initial_topic"], "notice")
        self.assertEqual(response.context["initial_length_style"], "medium")
        self.assertNotContains(response, "동의서로 이어서 만들기")

    def test_main_uses_workspace_cache_headers(self):
        response = self.client.get(reverse("noticegen:main"))
        self.assertEqual(response["Cache-Control"], "private, no-cache, must-revalidate")

    @patch("noticegen.views._call_deepseek")
    def test_generate_accepts_keywords_only_with_parent_notice_defaults(self, mock_call):
        mock_call.return_value = "가정통신문 안내를 확인해 주세요."

        response = self.client.post(
            reverse("noticegen:generate"),
            {"keywords": "가정통신문 안내"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "가정통신문 안내를 확인해 주세요.")
        user_prompt = mock_call.call_args.args[1]
        self.assertIn("대상: 학부모", user_prompt)
        self.assertIn("주제: 알림장", user_prompt)
        self.assertIn("분량: 보통", user_prompt)

    @patch("noticegen.views._call_deepseek")
    def test_generate_infers_event_context_from_messy_keywords(self, mock_call):
        mock_call.return_value = "내일 체험학습이 있어 8시 40분까지 등교할 수 있도록 도시락을 챙겨 보내 주세요."

        response = self.client.post(
            reverse("noticegen:generate"),
            {"keywords": "내일 체험학습\n8시 40분까지 등교, 도시락 챙겨 주세요"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        user_prompt = mock_call.call_args.args[1]
        self.assertIn("주제: 행사", user_prompt)
        self.assertIn("핵심 전달사항: 내일 체험학습, 8시 40분까지 등교, 도시락 챙겨 주세요", user_prompt)
        self.assertIn("추가 상황: 준비물, 일정 변경, 행사 안내", user_prompt)

    @patch("noticegen.views._call_deepseek")
    def test_generate_retries_once_when_first_output_misses_required_terms(self, mock_call):
        mock_call.side_effect = [
            "체험학습 안내입니다. 편한 복장으로 보내 주세요.",
            "3월 8일 체험학습 안내입니다. 도시락을 챙겨 보내 주세요.",
        ]

        response = self.client.post(
            reverse("noticegen:generate"),
            {"keywords": "3월 8일 체험학습, 도시락 챙겨 주세요"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "3월 8일 체험학습 안내입니다. 도시락을 챙겨 보내 주세요.")
        self.assertEqual(mock_call.call_count, 2)

    @patch("noticegen.views._call_deepseek")
    def test_generate_retries_once_when_output_adds_unverified_time(self, mock_call):
        mock_call.side_effect = [
            "내일 오전 9시에 체험학습이 있으니 도시락을 챙겨 보내 주세요.",
            "체험학습이 있으니 도시락을 챙겨 보내 주세요.",
        ]

        response = self.client.post(
            reverse("noticegen:generate"),
            {"keywords": "체험학습 안내, 도시락 챙겨 주세요"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "체험학습이 있으니 도시락을 챙겨 보내 주세요.")
        self.assertEqual(mock_call.call_count, 2)

    @patch("noticegen.views._call_deepseek")
    def test_result_panel_copy_button_has_failure_feedback(self, mock_call):
        mock_call.return_value = "준비물을 챙겨 주세요."
        response = self.client.post(
            reverse("noticegen:generate"),
            self._payload(),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "copyError: '', async copyText(text)", html=False)
        self.assertContains(response, '@click="copyText($refs.output.value)"', html=False)
        self.assertContains(response, "복사에 실패했습니다. 직접 선택해 복사해 주세요.")
        self.assertNotContains(response, "동의서로 이어서 만들기")
        self.assertNotContains(response, "서명으로 이어서 만들기")
        self.assertEqual(response["Cache-Control"], "no-store, private")

    @patch("noticegen.views._call_deepseek")
    def test_generate_mini_uses_sensitive_cache_headers(self, mock_call):
        mock_call.return_value = "준비물을 꼭 챙기세요."

        response = self.client.post(
            reverse("noticegen:generate_mini"),
            self._payload(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, private")

    @patch("noticegen.views._daily_limit", return_value=999)
    @patch("noticegen.views._call_deepseek")
    def test_generate_uses_burst_ratelimit_for_abnormal_pattern(self, mock_call, _mock_daily_limit):
        mock_call.return_value = "준비물을 꼭 챙겨 주세요."

        for index in range(30):
            response = self.client.post(
                reverse("noticegen:generate"),
                self._payload(keywords=f"체험학습 준비물 안내 {index}"),
                HTTP_HX_REQUEST="true",
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("noticegen:generate"),
            self._payload(keywords="체험학습 준비물 안내 초과"),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "짧은 시간에 생성 요청이 많았습니다.", status_code=429)

    def test_main_prefills_from_sheetbook_seed(self):
        session = self.client.session
        session["sheetbook_action_seeds"] = {
            "seed-token": {
                "action": "notice",
                "data": {
                    "target": "parent",
                    "topic": "notice",
                    "length_style": "medium",
                    "keywords": "체험학습 준비물 안내",
                },
            }
        }
        session.save()

        response = self.client.get(f"{reverse('noticegen:main')}?sb_seed=seed-token")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교무수첩에서 가져온 내용을 넣어두었어요.")
        self.assertContains(response, "체험학습 준비물 안내")
        self.assertEqual(response.context["initial_target"], "parent")
        self.assertEqual(response.context["initial_topic"], "notice")
