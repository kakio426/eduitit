from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from teacher_law.services.chat import answer_legal_question
from teacher_law.services.llm_client import _extract_json_payload
from teacher_law.services.query_normalizer import QUICK_QUESTIONS, build_query_profile


class QueryNormalizerTests(SimpleTestCase):
    def test_build_query_profile_expands_common_teacher_terms(self):
        profile = build_query_profile("학폭 알게 되면 교사가 먼저 뭐 해야 하나요?")
        self.assertEqual(profile["topic"], "school_violence")
        self.assertIn("학교폭력", profile["normalized_question"])
        self.assertTrue(profile["scope_supported"])
        self.assertTrue(profile["candidate_queries"])


class LlmPayloadParsingTests(SimpleTestCase):
    def test_extract_json_payload_handles_code_fence(self):
        payload = _extract_json_payload(
            '```json\n{"summary":"ok","action_items":["a"],"citations":[],"risk_level":"low","needs_human_help":false,"disclaimer":"d","scope_supported":true}\n```'
        )
        self.assertEqual(payload["summary"], "ok")

    def test_extract_json_payload_handles_explanatory_text(self):
        payload = _extract_json_payload(
            '먼저 정리했습니다.\n{"summary":"ok","action_items":["a"],"citations":[],"risk_level":"low","needs_human_help":false,"disclaimer":"d","scope_supported":true}\n이상입니다.'
        )
        self.assertEqual(payload["summary"], "ok")


@override_settings(
    TEACHER_LAW_ENABLED=True,
    TEACHER_LAW_FAQ_CACHE_TTL_SECONDS=43200,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "teacher-law-tests"}},
)
class TeacherLawCachingTests(TestCase):
    def tearDown(self):
        cache.clear()

    def test_quick_question_uses_cache_on_second_request(self):
        citation = {
            "citation_id": "law-1",
            "law_name": "학교폭력예방 및 대책에 관한 법률",
            "law_id": "123",
            "mst": "999",
            "article_label": "제1조",
            "quote": "학교폭력 예방과 대응에 관한 내용",
            "source_url": "https://www.law.go.kr",
            "fetched_at": "2026-04-05T00:00:00+09:00",
        }
        llm_answer = {
            "summary": "먼저 사안을 보고하고 절차를 시작해야 합니다.",
            "action_items": ["학교 관리자에게 즉시 공유합니다."],
            "citations": ["law-1"],
            "risk_level": "medium",
            "needs_human_help": False,
            "disclaimer": "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다.",
            "scope_supported": True,
        }
        with (
            patch("teacher_law.services.chat.is_law_api_configured", return_value=True),
            patch("teacher_law.services.chat.is_llm_configured", return_value=True),
            patch("teacher_law.services.chat.search_laws", return_value=[{"law_name": citation["law_name"], "law_id": "123", "mst": "999", "detail_link": citation["source_url"]}]) as search_mock,
            patch("teacher_law.services.chat.get_law_details", return_value={"law_name": citation["law_name"], "law_id": "123", "mst": "999", "detail_link": citation["source_url"], "articles": []}),
            patch("teacher_law.services.chat.select_relevant_citations", return_value=[citation]),
            patch("teacher_law.services.chat.generate_legal_answer", return_value=llm_answer),
        ):
            first = answer_legal_question(question=QUICK_QUESTIONS[0])
            second = answer_legal_question(question=QUICK_QUESTIONS[0])

        self.assertFalse(first["audit"]["cache_hit"])
        self.assertTrue(second["audit"]["cache_hit"])
        self.assertEqual(search_mock.call_count, 1)
