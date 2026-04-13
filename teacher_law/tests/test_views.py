import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from products.models import Product, ServiceManual
from teacher_law.models import LegalCitation, LegalChatMessage, LegalChatSession, LegalQueryAudit
from teacher_law.views import _build_page_context, ask_question_api, main_view


User = get_user_model()


def _build_user():
    return User.objects.create_user(
        username="teacher",
        email="teacher@example.com",
        password="testpass123!",
    )


@override_settings(
    TEACHER_LAW_ENABLED=True,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "teacher-law-view-tests"}},
)
class TeacherLawViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = _build_user()
        cache.clear()

    def _build_request_payload(self, question, **overrides):
        payload = {
            "question": question,
            "incident_type": "privacy_photo",
            "legal_goal": "posting_allowed",
            "scene": "",
            "counterpart": "student",
        }
        payload.update(overrides)
        return payload

    def _build_success_result(self, question="학생 사진 올려도 되나요?"):
        return {
            "status": "ok",
            "profile": {
                "original_question": question,
                "normalized_question": question,
                "topic": "privacy_photo",
                "scope_supported": True,
                "risk_flags": [],
                "candidate_queries": ["학생 사진 개인정보 보호법"],
                "quick_question_key": "",
            },
            "payload": {
                "summary": "보호자 동의 범위와 게시 장소를 먼저 확인해야 합니다.",
                "action_items": ["게시 장소를 먼저 정합니다."],
                "citations": [],
                "risk_level": "medium",
                "needs_human_help": False,
                "disclaimer": "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다.",
                "scope_supported": True,
            },
            "audit": {
                "cache_hit": False,
                "search_attempt_count": 1,
                "search_result_count": 2,
                "detail_fetch_count": 1,
                "selected_laws_json": [{"law_name": "개인정보 보호법"}],
                "failure_reason": "",
                "error_message": "",
                "elapsed_ms": 420,
            },
        }

    def test_main_view_renders_quick_questions(self):
        request = self.factory.get("/teacher-law/")
        request.user = self.user
        request.session = {}

        response = main_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교사용 AI 법률 가이드")
        self.assertContains(response, "지금 상황만 적어 주세요")
        self.assertContains(response, "예시 질문")
        self.assertContains(response, "사건 유형")
        self.assertContains(response, "지금 궁금한 것")
        self.assertContains(response, "안전사고·책임")
        self.assertContains(response, "학생 사진을 학급 밴드나 단체방에 올려도 되나요?")
        self.assertContains(response, "하루 15회")
        self.assertContains(response, "개별 사건의 법적 판단이나 결과를 보장하지 않습니다.")
        self.assertNotContains(response, "상황 입력 후 질문")
        self.assertNotContains(response, "입력 순서")
        self.assertNotContains(response, "빠르게 시작")
        self.assertNotContains(response, "빠른 질문")
        self.assertNotContains(response, "선택 후 질문")
        self.assertNotContains(response, "교실에서 바로 확인해야 할 법령만 빠르게 묻습니다")
        self.assertNotContains(response, "현재 상태")
        self.assertNotContains(response, "도와드리는 범위")

    @patch("teacher_law.views.is_law_api_configured", return_value=True)
    @patch("teacher_law.views.is_llm_configured", return_value=True)
    def test_main_view_splits_law_and_case_evidence_sections(self, _llm_mock, _law_mock):
        session = LegalChatSession.objects.create(user=self.user)
        user_message = LegalChatMessage.objects.create(
            session=session,
            role=LegalChatMessage.Role.USER,
            body="쉬는시간에 학생이 다쳤는데 교사 책임이 있나요?",
        )
        assistant_message = LegalChatMessage.objects.create(
            session=session,
            role=LegalChatMessage.Role.ASSISTANT,
            body="답변",
            payload_json={
                "summary": "학교안전사고 관련 법령과 판례를 함께 확인해야 합니다.",
                "action_items": ["사고 경위를 기록합니다."],
                "citations": [],
                "risk_level": "medium",
                "needs_human_help": False,
                "disclaimer": "",
                "scope_supported": True,
            },
        )
        LegalCitation.objects.create(
            message=assistant_message,
            law_name="학교안전사고 예방 및 보상에 관한 법률",
            law_id="009620",
            mst="",
            source_type=LegalCitation.SourceType.LAW,
            article_label="제2조",
            case_number="",
            quote="학교안전사고의 정의를 정한다.",
            source_url="",
            fetched_at=timezone.now(),
            display_order=1,
        )
        LegalCitation.objects.create(
            message=assistant_message,
            law_name="학교안전사고 손해배상",
            law_id="009620",
            mst="",
            source_type=LegalCitation.SourceType.CASE,
            article_label="2024다12345",
            case_number="2024다12345",
            quote="보호의무 위반 여부를 구체적 사정에 따라 판단했다.",
            source_url="",
            fetched_at=timezone.now(),
            display_order=2,
        )
        LegalQueryAudit.objects.create(
            session=session,
            user_message=user_message,
            assistant_message=assistant_message,
            original_question=user_message.body,
            normalized_question=user_message.body,
            topic="school_safety",
            scope_supported=True,
            risk_flags_json=[],
            candidate_queries_json=[],
            selected_laws_json=[],
            search_attempt_count=1,
            search_result_count=1,
            detail_fetch_count=1,
            cache_hit=False,
            elapsed_ms=100,
            failure_reason="",
            error_message="",
        )

        request = self.factory.get("/teacher-law/")
        request.user = self.user
        request.session = {}

        response = main_view(request)

        self.assertContains(response, "근거")
        self.assertContains(response, "기본 법령")
        self.assertContains(response, "참고 판례")
        self.assertContains(response, "학교안전사고 예방 및 보상에 관한 법률")
        self.assertContains(response, "학교안전사고 손해배상")

    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    @patch("teacher_law.views.is_llm_configured", return_value=True)
    def test_main_view_shows_beopmang_notice_without_law_api_warning(self, _llm_mock):
        request = self.factory.get("/teacher-law/")
        request.user = self.user
        request.session = {}

        response = main_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "법령 데이터는 법망(API.beopmang.org)을 통해 조회되며, 답변은 참고용입니다.")
        self.assertNotContains(response, "관리자가 아직 법령 연결을 마치지 않았습니다.")

    @patch("teacher_law.views.is_law_api_configured", return_value=True)
    @patch("teacher_law.views.is_llm_configured", return_value=False)
    def test_main_view_blocks_form_when_answer_pipeline_unavailable(self, _llm_mock, _law_mock):
        request = self.factory.get("/teacher-law/")
        request.user = self.user
        request.session = {}

        context = _build_page_context(request)
        response = main_view(request)

        self.assertTrue(context["ui_blocked"])
        self.assertIn("답변 연결", context["ui_block_reason"])
        self.assertContains(response, 'data-ui-blocked="true"')
        self.assertContains(response, 'data-teacher-law-input="true" placeholder=')
        self.assertContains(response, "disabled")

    @patch("teacher_law.views.is_law_api_configured", return_value=True)
    @patch("teacher_law.views.is_llm_configured", return_value=True)
    def test_page_context_builds_latest_pair_and_recent_history(self, _llm_mock, _law_mock):
        session = LegalChatSession.objects.create(user=self.user)
        for index in range(8):
            user_message = LegalChatMessage.objects.create(
                session=session,
                role=LegalChatMessage.Role.USER,
                body=f"질문 {index}",
            )
            assistant_message = LegalChatMessage.objects.create(
                session=session,
                role=LegalChatMessage.Role.ASSISTANT,
                body=f"답변 {index}",
                payload_json={
                    "summary": f"요약 {index}",
                    "action_items": [],
                    "citations": [],
                    "risk_level": "low",
                    "needs_human_help": False,
                    "disclaimer": "",
                    "scope_supported": True,
                },
            )
            LegalQueryAudit.objects.create(
                session=session,
                user_message=user_message,
                assistant_message=assistant_message,
                original_question=user_message.body,
                normalized_question=user_message.body,
                topic="privacy_photo",
                scope_supported=True,
                risk_flags_json=[],
                candidate_queries_json=[],
                selected_laws_json=[],
                search_attempt_count=1,
                search_result_count=1,
                detail_fetch_count=1,
                cache_hit=False,
                elapsed_ms=100,
                failure_reason="",
                error_message="",
            )

        request = self.factory.get("/teacher-law/")
        request.user = self.user
        request.session = {}

        context = _build_page_context(request)

        self.assertEqual(context["latest_pair"]["user_message"]["body"], "질문 7")
        self.assertEqual(context["latest_pair"]["assistant_message"]["summary"], "요약 7")
        self.assertEqual(len(context["history_pairs"]), 6)
        self.assertEqual(context["history_pairs"][0]["user_message"]["body"], "질문 6")
        self.assertEqual(context["history_pairs"][-1]["user_message"]["body"], "질문 1")

    @override_settings(TEACHER_LAW_DAILY_LIMIT_PER_USER=1)
    def test_ask_api_returns_429_after_daily_limit(self):
        first_request = self.factory.post(
            "/teacher-law/ask/",
            data=json.dumps(self._build_request_payload("학생 사진 올려도 되나요?")),
            content_type="application/json",
        )
        first_request.user = self.user

        second_request = self.factory.post(
            "/teacher-law/ask/",
            data=json.dumps(
                self._build_request_payload(
                    "학부모가 민원을 넣겠다고 합니다.",
                    incident_type="education_activity",
                    legal_goal="immediate_action",
                    counterpart="parent",
                )
            ),
            content_type="application/json",
        )
        second_request.user = self.user

        with patch("teacher_law.views.answer_legal_question", return_value=self._build_success_result()):
            first_response = ask_question_api(first_request)
        with patch("teacher_law.views.answer_legal_question", return_value=self._build_success_result("학부모가 민원을 넣겠다고 합니다.")):
            second_response = ask_question_api(second_request)

        second_payload = json.loads(second_response.content)
        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 429)
        self.assertIn("오늘 질문 1회를 모두 사용했어요.", second_payload["message"])
        self.assertEqual(LegalQueryAudit.objects.count(), 1)

    @override_settings(TEACHER_LAW_DAILY_LIMIT_PER_USER=1)
    @patch("teacher_law.views.is_law_api_configured", return_value=True)
    @patch("teacher_law.views.is_llm_configured", return_value=True)
    def test_main_view_blocks_form_when_daily_limit_is_reached(self, _llm_mock, _law_mock):
        request = self.factory.post(
            "/teacher-law/ask/",
            data=json.dumps(self._build_request_payload("학생 사진 올려도 되나요?")),
            content_type="application/json",
        )
        request.user = self.user

        with patch("teacher_law.views.answer_legal_question", return_value=self._build_success_result()):
            ask_question_api(request)

        page_request = self.factory.get("/teacher-law/")
        page_request.user = self.user
        page_request.session = {}

        context = _build_page_context(page_request)
        response = main_view(page_request)

        self.assertTrue(context["ui_blocked"])
        self.assertIn("오늘 질문 1회를 모두 사용했어요.", context["ui_block_reason"])
        self.assertContains(response, 'data-ui-blocked="true"')
        self.assertContains(response, "오늘 질문 1회를 모두 사용했어요.")

    @override_settings(TEACHER_LAW_DAILY_LIMIT_PER_USER=1)
    def test_failed_request_does_not_consume_daily_limit(self):
        failed_request = self.factory.post(
            "/teacher-law/ask/",
            data=json.dumps(self._build_request_payload("학생 사진 올려도 되나요?")),
            content_type="application/json",
        )
        failed_request.user = self.user

        success_request = self.factory.post(
            "/teacher-law/ask/",
            data=json.dumps(self._build_request_payload("학생 사진 올려도 되나요?")),
            content_type="application/json",
        )
        success_request.user = self.user

        llm_error = __import__("teacher_law.services.llm_client", fromlist=["LlmClientError"]).LlmClientError("boom")
        with patch("teacher_law.views.answer_legal_question", side_effect=llm_error):
            failed_response = ask_question_api(failed_request)
        with patch("teacher_law.views.answer_legal_question", return_value=self._build_success_result()):
            success_response = ask_question_api(success_request)

        self.assertEqual(failed_response.status_code, 503)
        self.assertEqual(success_response.status_code, 201)
        self.assertEqual(LegalQueryAudit.objects.count(), 2)

    def test_ask_api_missing_structured_fields_returns_400_without_saving_messages(self):
        request = self.factory.post(
            "/teacher-law/ask/",
            data=json.dumps({"question": "학생 사진 올려도 되나요?"}),
            content_type="application/json",
        )
        request.user = self.user

        response = ask_question_api(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 400)
        self.assertIn("field_errors", payload)
        self.assertIn("incident_type", payload["field_errors"])
        self.assertEqual(LegalChatMessage.objects.count(), 0)
        self.assertEqual(LegalQueryAudit.objects.count(), 0)

    def test_ask_api_missing_law_api_key_returns_503(self):
        request = self.factory.post(
            "/teacher-law/ask/",
            data=json.dumps(self._build_request_payload("학생 사진 올려도 되나요?")),
            content_type="application/json",
        )
        request.user = self.user

        with patch("teacher_law.views.answer_legal_question", side_effect=__import__("teacher_law.services.law_api", fromlist=["LawApiConfigError"]).LawApiConfigError("missing")):
            response = ask_question_api(request)

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 503)
        self.assertIn("법령 연결", payload["message"])

    def test_ask_api_saves_assistant_message_citations_and_audit(self):
        request = self.factory.post(
            "/teacher-law/ask/",
            data=json.dumps(self._build_request_payload("학생 사진 올려도 되나요?")),
            content_type="application/json",
        )
        request.user = self.user
        result = self._build_success_result()
        result["payload"]["citations"] = [
            {
                "citation_id": "law-1",
                "source_type": "law",
                "title": "개인정보 보호법",
                "law_name": "개인정보 보호법",
                "law_id": "123",
                "mst": "456",
                "reference_label": "제15조",
                "article_label": "제15조",
                "case_number": "",
                "quote": "개인정보 처리와 동의에 관한 조문",
                "source_url": "https://www.law.go.kr",
                "provider": "beopmang",
                "fetched_at": "2026-04-05T00:00:00+09:00",
            },
            {
                "citation_id": "case-1",
                "source_type": "case",
                "title": "학생 사진 게시 분쟁",
                "law_name": "학생 사진 게시 분쟁",
                "law_id": "123",
                "mst": "",
                "reference_label": "2024다12345",
                "article_label": "2024다12345",
                "case_number": "2024다12345",
                "quote": "게시 범위와 동의 여부를 함께 봤다.",
                "source_url": "",
                "provider": "beopmang",
                "fetched_at": "2026-04-05T00:00:00+09:00",
            }
        ]

        with patch("teacher_law.views.answer_legal_question", return_value=result):
            response = ask_question_api(request)

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(LegalChatMessage.objects.filter(role="assistant").count(), 1)
        self.assertEqual(LegalCitation.objects.count(), 2)
        self.assertEqual(LegalQueryAudit.objects.count(), 1)
        self.assertEqual(payload["assistant_message"]["citations"][0]["law_name"], "개인정보 보호법")
        self.assertEqual(payload["assistant_message"]["citations"][1]["source_type"], "case")
        self.assertEqual(payload["assistant_message"]["case_citations"][0]["case_number"], "2024다12345")


class EnsureTeacherLawCommandTests(TestCase):
    def test_ensure_teacher_law_creates_product_and_manual(self):
        call_command("ensure_teacher_law")

        product = Product.objects.get(launch_route_name="teacher_law:main")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(product.title, "교사용 AI 법률 가이드")
        self.assertEqual(product.features.count(), 3)
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)
