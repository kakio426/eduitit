import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings

from products.models import Product, ServiceManual
from teacher_law.models import LegalCitation, LegalChatMessage, LegalQueryAudit
from teacher_law.views import ask_question_api, main_view


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

    def test_main_view_renders_quick_questions(self):
        request = self.factory.get("/teacher-law/")
        request.user = self.user
        request.session = {}

        response = main_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교사용 AI 법률 가이드")
        self.assertContains(response, "학생 사진을 학급 밴드나 단체방에 올려도 되나요?")

    def test_ask_api_out_of_scope_returns_scope_supported_false(self):
        request = self.factory.post(
            "/teacher-law/ask/",
            data=json.dumps({"question": "중고거래 환불은 어떻게 되나요?"}),
            content_type="application/json",
        )
        request.user = self.user

        response = ask_question_api(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 201)
        self.assertFalse(payload["assistant_message"]["scope_supported"])
        self.assertEqual(LegalQueryAudit.objects.count(), 1)

    def test_ask_api_missing_law_api_key_returns_503(self):
        request = self.factory.post(
            "/teacher-law/ask/",
            data=json.dumps({"question": "학생 사진 올려도 되나요?"}),
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
            data=json.dumps({"question": "학생 사진 올려도 되나요?"}),
            content_type="application/json",
        )
        request.user = self.user
        result = {
            "profile": {
                "original_question": "학생 사진 올려도 되나요?",
                "normalized_question": "학생 사진 올려도 되나요?",
                "topic": "privacy_photo",
                "scope_supported": True,
                "risk_flags": [],
                "candidate_queries": ["학생 사진 개인정보 보호법"],
                "quick_question_key": "",
            },
            "payload": {
                "summary": "보호자 동의 범위와 게시 장소를 먼저 확인해야 합니다.",
                "action_items": ["게시 장소를 먼저 정합니다."],
                "citations": [
                    {
                        "citation_id": "law-1",
                        "law_name": "개인정보 보호법",
                        "law_id": "123",
                        "mst": "456",
                        "article_label": "제15조",
                        "quote": "개인정보 처리와 동의에 관한 조문",
                        "source_url": "https://www.law.go.kr",
                        "fetched_at": "2026-04-05T00:00:00+09:00",
                    }
                ],
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

        with patch("teacher_law.views.answer_legal_question", return_value=result):
            response = ask_question_api(request)

        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(LegalChatMessage.objects.filter(role="assistant").count(), 1)
        self.assertEqual(LegalCitation.objects.count(), 1)
        self.assertEqual(LegalQueryAudit.objects.count(), 1)
        self.assertEqual(payload["assistant_message"]["citations"][0]["law_name"], "개인정보 보호법")


class EnsureTeacherLawCommandTests(TestCase):
    def test_ensure_teacher_law_creates_product_and_manual(self):
        call_command("ensure_teacher_law")

        product = Product.objects.get(launch_route_name="teacher_law:main")
        manual = ServiceManual.objects.get(product=product)

        self.assertEqual(product.title, "교사용 AI 법률 가이드")
        self.assertEqual(product.features.count(), 3)
        self.assertTrue(manual.is_published)
        self.assertGreaterEqual(manual.sections.count(), 3)
