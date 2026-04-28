from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile

from .daily_recommendations import (
    build_daily_recommendation_context,
    build_daily_safety_topic_catalog,
    get_or_create_daily_recommendation,
)
from .models import DailyNoticeRecommendation, NoticeGenerationAttempt, NoticeGenerationCache
from .prompts import (
    LENGTH_LONG,
    LENGTH_MEDIUM,
    LENGTH_SHORT,
    PROMPT_VERSION,
    build_system_prompt,
    build_user_prompt,
    get_tone_for_target,
)
from .views import (
    _build_cache_key_data,
    _build_page_context,
    _build_retry_user_prompt,
    _collect_output_quality_issues,
)


class NoticeGenViewTests(TestCase):
    def _payload(self, **kwargs):
        base = {
            "target": "student_low",
            "topic": "safety",
            "keywords": "물병을 꼭 챙기고 쉬는 시간에는 그늘에서 쉬기",
        }
        base.update(kwargs)
        return base

    def test_guest_trial_limit_is_2(self):
        session = self.client.session
        session.save()
        session_key = session.session_key

        for _ in range(2):
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
        self.assertEqual(response["HX-Retarget"], "#noticegen-form-status")
        self.assertContains(response, "오늘 한도", status_code=429)
        self.assertContains(response, "로그인하고 계속", status_code=429)

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
        self.assertEqual(response["HX-Retarget"], "#noticegen-form-status")
        self.assertContains(response, "오늘 한도", status_code=429)

    def test_guest_trial_limit_blocks_even_when_cache_exists(self):
        session = self.client.session
        session.save()
        session_key = session.session_key

        for _ in range(2):
            NoticeGenerationAttempt.objects.create(
                session_key=session_key,
                target="parent",
                topic="notice",
                tone=get_tone_for_target("parent"),
                charged=True,
                status=NoticeGenerationAttempt.STATUS_LLM_SUCCESS,
            )

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
            result_text="준비물을 꼭 챙겨주세요.",
        )

        response = self.client.post(
            reverse("noticegen:generate"),
            payload,
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "오늘 한도", status_code=429)

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

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response["HX-Retarget"], "#noticegen-form-status")
        self.assertContains(response, "다시 시도", status_code=503)
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
        self.assertContains(response, "전달 사항 필요", status_code=400)

    def test_generate_mini_guest_limit_uses_compact_error_panel(self):
        session = self.client.session
        session.save()
        session_key = session.session_key

        for _ in range(2):
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
        self.assertContains(response, "오늘 한도", status_code=429)
        self.assertContains(response, "로그인", status_code=429)

    def test_parent_prompt_has_length_and_natural_flow_rules(self):
        system_prompt = build_system_prompt("parent", LENGTH_LONG)
        user_prompt = build_user_prompt("parent", "notice", "실내화를 챙겨 주세요", "", LENGTH_LONG)

        self.assertEqual(PROMPT_VERSION, "v6-caveman")
        self.assertLess(len(system_prompt), 650)
        self.assertLess(len(user_prompt), 320)
        self.assertIn("분량 규칙", system_prompt)
        self.assertIn("선택 분량: 길게", system_prompt)
        self.assertIn("문장은 한 단락처럼 자연스럽게 연결", system_prompt)
        self.assertNotIn("정확히 3문장", system_prompt)
        self.assertIn("문어체", system_prompt)
        self.assertIn("거예요", system_prompt)
        self.assertIn("않을 거야", system_prompt)
        self.assertIn("학부모가 바로 받아 읽는 가정통신문/알림장 문장", system_prompt)
        self.assertIn("운동화를 신고오도록 안내해 주세요", system_prompt)
        self.assertIn("분량: 길게", user_prompt)
        self.assertIn("공백 포함 180~260자", user_prompt)
        self.assertIn("문어체 공지문", user_prompt)
        self.assertIn("학부모에게 직접 보내는 완성 문장", user_prompt)
        self.assertIn("안내해 주세요", user_prompt)

    def test_retry_prompt_uses_compact_caveman_correction(self):
        retry_prompt = _build_retry_user_prompt(
            "기본 프롬프트",
            ["TOO_SHORT:medium", "MISSING_TERMS:도시락", "UNVERIFIED_DETAILS:오전 9시"],
            target="parent",
            length_style=LENGTH_MEDIUM,
            result_text="짧은 초안입니다.",
        )

        self.assertIn("직전:", retry_prompt)
        self.assertIn("수정:", retry_prompt)
        self.assertIn("너무 짧음", retry_prompt)
        self.assertIn("누락 포함: 도시락", retry_prompt)
        self.assertIn("입력에 없는 정보 제거: 오전 9시", retry_prompt)
        self.assertNotIn("직전 출력이 너무 짧았습니다", retry_prompt)
        self.assertLess(len(retry_prompt), 170)

    def test_default_page_context_starts_with_parent_target(self):
        page_context = _build_page_context()
        self.assertEqual(page_context["initial_target"], "parent")

    def test_medium_parent_prompt_requests_fuller_default_length(self):
        user_prompt = build_user_prompt("parent", "event", "탄천 생태체험, 운동화 착용", "", LENGTH_MEDIUM)
        self.assertIn("공백 포함 140~220자", user_prompt)
        self.assertIn("상황 안내, 핵심 준비/행동 안내, 마무리 당부", user_prompt)

    def test_output_quality_flags_parent_meta_instruction(self):
        issues = _collect_output_quality_issues(
            "체험활동에 적합하도록 운동화를 신고오도록 안내해 주세요.",
            "탄천 생태체험, 운동화 착용",
            [],
            target="parent",
            length_style=LENGTH_MEDIUM,
        )

        self.assertIn("PARENT_META_INSTRUCTION", issues)

    def test_output_quality_flags_too_short_for_medium_length(self):
        issues = _collect_output_quality_issues(
            "체험학습 준비물을 확인해 주시기 바랍니다.",
            "체험학습, 준비물 확인",
            ["체험학습", "준비물"],
            target="parent",
            length_style=LENGTH_MEDIUM,
        )

        self.assertTrue(any(issue.startswith("TOO_SHORT:") for issue in issues))

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
        self.assertContains(response, "남은 체험")
        self.assertEqual(response.context["remaining_count"], 2)
        self.assertEqual(response.context["daily_limit"], 2)
        self.assertContains(response, "알림장·주간학습 멘트")
        self.assertContains(response, "직접 조정")
        self.assertContains(response, "생성 결과")
        self.assertContains(response, "문장 만들기")
        self.assertEqual(response.context["initial_target"], "parent")
        self.assertEqual(response.context["initial_topic"], "notice")
        self.assertEqual(response.context["initial_length_style"], "medium")
        self.assertNotContains(response, "동의서로 이어서 만들기")

    def test_main_shows_login_gate_when_guest_trial_is_complete(self):
        session = self.client.session
        session.save()
        session_key = session.session_key
        for _ in range(2):
            NoticeGenerationAttempt.objects.create(
                session_key=session_key,
                target="student_low",
                topic="safety",
                tone=get_tone_for_target("student_low"),
                charged=True,
                status=NoticeGenerationAttempt.STATUS_LLM_SUCCESS,
            )

        response = self.client.get(reverse("noticegen:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "비회원 체험 2회 완료")
        self.assertContains(response, "로그인 후 계속 작성합니다.")
        self.assertNotContains(response, "문장 만들기")

    def test_main_uses_workspace_cache_headers(self):
        response = self.client.get(reverse("noticegen:main"))
        self.assertEqual(response["Cache-Control"], "private, no-cache, must-revalidate")

    def test_main_uses_inline_loading_and_brand_accent(self):
        response = self.client.get(reverse("noticegen:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "noticegen-inline-loading")
        self.assertContains(response, "from-indigo-600")
        self.assertNotContains(response, "noticegen-loading")
        self.assertNotContains(response, "z-[120]")
        self.assertNotContains(response, "bg-[#E0E5EC]")
        self.assertNotContains(response, "from-blue-500")
        self.assertNotContains(response, "to-cyan-500")

    def test_generate_validation_error_targets_form_status_and_result_state(self):
        response = self.client.post(
            reverse("noticegen:generate"),
            self._payload(keywords=""),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["HX-Retarget"], "#noticegen-form-status")
        self.assertEqual(response["HX-Reswap"], "outerHTML")
        self.assertEqual(response["HX-Noticegen-Error"], "true")
        self.assertContains(response, 'id="noticegen-form-status"', status_code=400)
        self.assertContains(response, "전달 사항 필요", status_code=400)
        self.assertContains(response, 'id="noticegen-result" hx-swap-oob="innerHTML"', status_code=400)

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
        self.assertContains(response, "다시 시도", status_code=429)

    def test_main_prefills_from_workflow_seed(self):
        session = self.client.session
        session["workflow_action_seeds"] = {
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
        self.assertContains(response, "이전에 정리한 내용을 넣어두었어요.")
        self.assertContains(response, "체험학습 준비물 안내")
        self.assertEqual(response.context["initial_target"], "parent")
        self.assertEqual(response.context["initial_topic"], "notice")


class DailyNoticeRecommendationTests(TestCase):
    art_tools_text = (
        "오늘 학급에서는 미술도구를 사용할 때 가위와 풀, 색칠도구를 안전하게 쓰는 약속을 함께 확인했습니다. "
        "하교 후에도 가정에서 준비물을 정리하며 날카로운 도구를 장난처럼 쓰지 않도록 살펴봐 주시기 바랍니다."
    )
    dust_break_text = (
        "오늘 학급에서는 미세먼지가 많은 날 실외활동과 개인위생을 조절하는 안전수칙을 함께 확인했습니다. "
        "하교 후에도 가정에서 손 씻기와 옷 털기를 한 번 더 살펴봐 주시기 바랍니다."
    )
    dust_dismissal_text = (
        "오늘 학급에서는 하교 전 미세먼지가 많은 날 실외활동을 줄이고 개인위생을 챙기는 방법을 확인했습니다. "
        "가정에서도 손 씻기와 외출 뒤 옷 정리를 함께 살펴봐 주시기 바랍니다."
    )

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="daily-teacher",
            password="pw123456",
            email="daily@example.com",
        )
        profile = UserProfile.objects.get(user=self.user)
        profile.nickname = "담임"
        profile.save(update_fields=["nickname"])

    def _post_daily_recommendation(self):
        return self.client.post(
            reverse("noticegen:daily_recommendation"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_topic_catalog_has_no_duplicate_keys_for_365_days(self):
        catalog = build_daily_safety_topic_catalog()
        keys = [item["key"] for item in catalog[:365]]

        self.assertEqual(len(keys), 365)
        self.assertEqual(len(set(keys)), 365)

    def test_holiday_eve_context_prioritizes_special_public_holiday(self):
        context = build_daily_recommendation_context(date(2026, 5, 4))

        self.assertEqual(context["holiday_eve"], "어린이날")
        self.assertIn("어린이날 전날", context["context_label"])

    def test_substitute_holiday_eve_context_prioritizes_substitute_public_holiday(self):
        context = build_daily_recommendation_context(date(2026, 3, 1))

        self.assertEqual(context["holiday_eve"], "삼일절 대체공휴일")
        self.assertIn("삼일절 대체공휴일 전날", context["context_label"])

    @patch("noticegen.daily_recommendations.timezone.localdate", return_value=date(2026, 6, 10))
    @patch("noticegen.daily_recommendations._call_daily_recommendation_llm")
    def test_endpoint_generates_once_per_date_and_serves_same_text(self, mock_call, _mock_today):
        mock_call.return_value = self.art_tools_text
        self.client.force_login(self.user)

        first_response = self._post_daily_recommendation()
        second_response = self._post_daily_recommendation()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_payload = first_response.json()
        second_payload = second_response.json()
        self.assertEqual(first_payload["result_text"], self.art_tools_text)
        self.assertEqual(second_payload["result_text"], self.art_tools_text)
        self.assertEqual(first_payload["recommendation"]["date"], "2026-06-10")
        self.assertEqual(mock_call.call_count, 1)
        recommendation = DailyNoticeRecommendation.objects.get(recommendation_date=date(2026, 6, 10))
        self.assertEqual(recommendation.served_count, 2)

    @patch("noticegen.daily_recommendations._call_daily_recommendation_llm")
    def test_adjacent_dates_use_different_topic_keys(self, mock_call):
        mock_call.side_effect = [
            self.dust_break_text,
            self.dust_dismissal_text,
        ]

        first, _created, _generating = get_or_create_daily_recommendation(date(2026, 4, 26))
        second, _created, _generating = get_or_create_daily_recommendation(date(2026, 4, 27))

        self.assertNotEqual(first.topic_key, second.topic_key)

    @patch("noticegen.daily_recommendations.timezone.localdate", return_value=date(2026, 6, 10))
    @patch("noticegen.daily_recommendations._call_daily_recommendation_llm")
    def test_topic_mismatch_retries_before_saving_official_recommendation(self, mock_call, _mock_today):
        mock_call.side_effect = [
            (
                "오늘 학급에서는 비 오는 날 우산 시야와 젖은 바닥 미끄럼 안전수칙을 함께 확인했습니다. "
                "하교 후에도 뛰지 않고 주변을 살피며, 가정에서도 우산과 여벌 양말을 챙겨 주시기 바랍니다."
            ),
            self.art_tools_text,
        ]
        self.client.force_login(self.user)

        response = self._post_daily_recommendation()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["result_text"], self.art_tools_text)
        self.assertEqual(mock_call.call_count, 2)
        recommendation = DailyNoticeRecommendation.objects.get(recommendation_date=date(2026, 6, 10))
        self.assertEqual(recommendation.status, DailyNoticeRecommendation.STATUS_READY)

    @patch("noticegen.daily_recommendations.timezone.localdate", return_value=date(2026, 3, 6))
    @patch("noticegen.daily_recommendations._call_daily_recommendation_llm")
    def test_political_output_falls_back_without_500(self, mock_call, _mock_today):
        mock_call.return_value = "오늘은 선거와 정당 이야기를 중심으로 안전을 확인했습니다."
        self.client.force_login(self.user)

        response = self._post_daily_recommendation()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertNotIn("선거", payload["result_text"])
        recommendation = DailyNoticeRecommendation.objects.get(recommendation_date=date(2026, 3, 6))
        self.assertEqual(recommendation.status, DailyNoticeRecommendation.STATUS_FALLBACK)
        self.assertIn("POLITICAL_OUTPUT", recommendation.error_code)
        self.assertEqual(mock_call.call_count, 2)

    @patch("noticegen.daily_recommendations.timezone.localdate", return_value=date(2026, 3, 7))
    @patch("noticegen.daily_recommendations._call_daily_recommendation_llm", side_effect=TimeoutError("timeout"))
    def test_llm_failure_returns_fallback_json(self, _mock_call, _mock_today):
        self.client.force_login(self.user)

        response = self._post_daily_recommendation()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("오늘 학급에서는", payload["result_text"])
        recommendation = DailyNoticeRecommendation.objects.get(recommendation_date=date(2026, 3, 7))
        self.assertEqual(recommendation.status, DailyNoticeRecommendation.STATUS_FALLBACK)
