from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from teacher_law.services import law_api
from teacher_law.services.chat import answer_legal_question
from teacher_law.services.llm_client import _extract_json_payload
from teacher_law.services.law_api import LawApiError, LawApiTimeoutError, LawApiVerificationError
from teacher_law.services.query_normalizer import (
    build_query_profile,
    get_quick_question_presets,
    validate_structured_input,
)


class QueryNormalizerTests(SimpleTestCase):
    def test_build_query_profile_expands_common_teacher_terms(self):
        profile = build_query_profile("학폭 알게 되면 교사가 먼저 뭐 해야 하나요?")
        self.assertEqual(profile["topic"], "school_violence")
        self.assertIn("학교폭력", profile["normalized_question"])
        self.assertTrue(profile["scope_supported"])
        self.assertTrue(profile["candidate_queries"])

    def test_build_query_profile_supports_parent_verbal_abuse_question(self):
        profile = build_query_profile("학부모가 상담 중에 저에게 욕을 했습니다. 어떻게 해야 하나요?")

        self.assertEqual(profile["topic"], "education_activity")
        self.assertTrue(profile["scope_supported"])
        self.assertIn("교원의 지위 향상 및 교육활동 보호를 위한 특별법", profile["hint_queries"])

    def test_build_query_profile_supports_teacher_context_legal_question_even_without_fixed_topic(self):
        profile = build_query_profile("학부모가 저를 몰래 녹음해서 공개하면 법적으로 어떻게 대응하나요?")

        self.assertTrue(profile["scope_supported"])
        self.assertTrue(profile["candidate_queries"])

    def test_build_query_profile_structures_school_safety_liability_question(self):
        profile = build_query_profile("쉬는시간에 제가 교실에 있었는데 학생이 다쳤습니다. 교사인 제 법적 책임이 있나요?")

        self.assertEqual(profile["topic"], "school_safety")
        self.assertEqual(profile["incident_type"], "school_safety")
        self.assertIn("학생", profile["actors"])
        self.assertIn("쉬는시간", profile["scene"])
        self.assertIn("법적 책임", profile["legal_issues"])
        self.assertIn("학교안전사고 예방 및 보상에 관한 법률", profile["hint_queries"])
        self.assertIn("민법", profile["hint_queries"])
        self.assertEqual(profile["legal_goal"], "teacher_liability")
        self.assertIn("안전사고·책임 교사 책임이 있는지", profile["candidate_queries"])

    def test_build_query_profile_prefers_structured_input_over_free_text_only_guess(self):
        profile = build_query_profile(
            "학생 사진을 올려도 되나요?",
            incident_type="privacy_photo",
            legal_goal="posting_allowed",
            counterpart="student",
        )

        self.assertEqual(profile["incident_type"], "privacy_photo")
        self.assertEqual(profile["legal_goal"], "posting_allowed")
        self.assertEqual(profile["counterpart_label"], "학생")
        self.assertEqual(profile["law_allowlist"], ["개인정보 보호법", "초ㆍ중등교육법"])

    def test_build_query_profile_keeps_personal_life_legal_question_out_of_scope(self):
        profile = build_query_profile("중고거래 환불이 안 되는데 어떻게 대응하나요?")

        self.assertFalse(profile["scope_supported"])

    def test_validate_structured_input_requires_scene_for_school_safety(self):
        field_errors = validate_structured_input(
            incident_type="school_safety",
            legal_goal="teacher_liability",
            scene="",
            counterpart="",
        )

        self.assertIn("scene", field_errors)


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


class OpenLawRequestTests(SimpleTestCase):
    @override_settings(TEACHER_LAW_PROVIDER="open_law")
    @patch.dict("os.environ", {"LAW_API_OC": "test-oc"}, clear=False)
    def test_request_falls_back_to_http_when_https_connection_fails(self):
        success_response = Mock()
        success_response.json.return_value = {"result": "success", "LawSearch": {"law": []}}

        def fake_get(url, **kwargs):
            if url.startswith("https://"):
                raise law_api.requests.ConnectionError("connection reset by peer")
            return success_response

        with patch("teacher_law.services.law_api.requests.get", side_effect=fake_get) as request_mock:
            payload = law_api._request("lawSearch.do", params={"target": "law"}, timeout_seconds=4)

        self.assertEqual(payload["result"], "success")
        attempted_urls = [call.args[0] for call in request_mock.call_args_list]
        self.assertEqual(attempted_urls[0], "https://www.law.go.kr/DRF/lawSearch.do")
        self.assertEqual(attempted_urls[1], "http://www.law.go.kr/DRF/lawSearch.do")

    @override_settings(TEACHER_LAW_PROVIDER="open_law")
    @patch.dict("os.environ", {"LAW_API_OC": "test-oc"}, clear=False)
    def test_request_raises_verification_error_with_domain_ip_message(self):
        verification_response = Mock()
        verification_response.json.return_value = {
            "result": "사용자 정보 검증에 실패하였습니다.",
            "msg": "OPEN API 호출 시 사용자 검증을 위하여 정확한 서버장비의 IP주소 및 도메인주소를 등록해 주세요.",
        }

        with patch("teacher_law.services.law_api.requests.get", return_value=verification_response):
            with self.assertRaises(LawApiVerificationError) as caught:
                law_api._request("lawSearch.do", params={"target": "law"}, timeout_seconds=4)

        self.assertIn("IP주소", str(caught.exception))


class BeopmangLawApiTests(SimpleTestCase):
    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    @patch.dict("os.environ", {}, clear=True)
    def test_is_configured_without_law_api_oc(self):
        self.assertTrue(law_api.is_configured())

    @override_settings(TEACHER_LAW_PROVIDER="beopmang", TEACHER_LAW_SEARCH_RESULT_LIMIT=5)
    def test_search_laws_maps_beopmang_results(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "success": True,
            "data": {
                "results": [
                    {
                        "law_id": "001706",
                        "law_name": "민법",
                        "law_type": "법률",
                        "enforcement_date": "2025-01-01",
                        "last_amended": "2024-12-31",
                    }
                ]
            },
        }

        with patch("teacher_law.services.law_api.requests.get", return_value=response) as request_mock:
            results = law_api.search_laws("민법")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["law_name"], "민법")
        self.assertEqual(results[0]["law_id"], "001706")
        self.assertEqual(results[0]["provider"], "beopmang")
        self.assertEqual(results[0]["mst"], "")
        params = request_mock.call_args.kwargs["params"]
        self.assertEqual(params["action"], "search")
        self.assertEqual(params["mode"], "keyword")

    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    def test_get_law_details_maps_grep_articles(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "success": True,
            "data": {
                "law_id": "001706",
                "law_type": "법률",
                "articles": [
                    {
                        "label": "제750조",
                        "full_text": "제750조(불법행위의 내용) 고의 또는 과실로 인한 손해배상 책임이 있다.",
                    }
                ],
            },
        }

        with patch("teacher_law.services.law_api.requests.get", return_value=response) as request_mock:
            details = law_api.get_law_details(law_id="001706", query_hint="손해배상", law_name="민법")

        self.assertEqual(details["law_name"], "민법")
        self.assertEqual(details["provider"], "beopmang")
        self.assertEqual(details["articles"][0]["article_label"], "제750조")
        self.assertIn("손해배상", details["articles"][0]["article_text"])
        params = request_mock.call_args.kwargs["params"]
        self.assertEqual(params["action"], "get")
        self.assertEqual(params["grep"], "손해배상")

    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    def test_get_law_details_falls_back_to_overview_when_grep_is_empty(self):
        grep_response = Mock(status_code=200)
        grep_response.json.return_value = {
            "success": True,
            "data": {
                "law_id": "001706",
                "law_name": "민법",
                "articles": [],
            },
        }
        overview_response = Mock(status_code=200)
        overview_response.json.return_value = {
            "success": True,
            "data": {
                "law_id": "001706",
                "law_name": "민법",
                "top_articles": [
                    {
                        "label": "제214조",
                        "snippet": "소유자는 방해의 제거와 손해배상의 담보를 청구할 수 있다.",
                    }
                ],
            },
        }

        with patch(
            "teacher_law.services.law_api.requests.get",
            side_effect=[grep_response, overview_response],
        ) as request_mock:
            details = law_api.get_law_details(law_id="001706", query_hint="손해배상")

        self.assertEqual(len(details["articles"]), 1)
        self.assertEqual(details["articles"][0]["article_label"], "제214조")
        self.assertIn("손해배상", details["articles"][0]["article_text"])
        first_params = request_mock.call_args_list[0].kwargs["params"]
        second_params = request_mock.call_args_list[1].kwargs["params"]
        self.assertEqual(first_params["action"], "get")
        self.assertEqual(second_params["action"], "overview")
        self.assertEqual(second_params["q"], "손해배상")

    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    def test_beopmang_429_maps_to_law_api_error(self):
        response = Mock(status_code=429)
        response.json.return_value = {"detail": "rate limited"}

        with patch("teacher_law.services.law_api.requests.get", return_value=response):
            with self.assertRaises(LawApiError):
                law_api.search_laws("민법")

    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    def test_beopmang_timeout_maps_to_timeout_error(self):
        with patch("teacher_law.services.law_api.requests.get", side_effect=law_api.requests.Timeout("timeout")):
            with self.assertRaises(LawApiTimeoutError):
                law_api.search_laws("민법")

    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    def test_search_cases_maps_beopmang_results(self):
        response = Mock(status_code=200)
        response.json.return_value = {
            "success": True,
            "data": {
                "results": [
                    {
                        "case_id": "case-1",
                        "title": "학교안전사고 손해배상",
                        "name": "2024다12345",
                        "summary": "교사의 보호의무와 과실 판단을 검토했다.",
                        "url": "https://api.beopmang.org/case/1",
                    }
                ]
            },
        }

        with patch("teacher_law.services.law_api.requests.get", return_value=response) as request_mock:
            results = law_api.search_cases("학교안전사고 손해배상", law_id="009620", article="750")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "학교안전사고 손해배상")
        self.assertEqual(results[0]["case_number"], "2024다12345")
        self.assertEqual(results[0]["source_type"], "case")
        params = request_mock.call_args.kwargs["params"]
        self.assertEqual(params["action"], "search")
        self.assertEqual(params["law_id"], "009620")
        self.assertEqual(params["article"], "750")

    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    def test_resolve_law_by_name_prefers_exact_law_over_enforcement_rule(self):
        cache.clear()
        with patch(
            "teacher_law.services.law_api.search_laws",
            return_value=[
                {"law_name": "학교안전사고 예방 및 보상에 관한 법률 시행규칙", "law_id": "rule-1", "mst": "", "law_type": "교육부령", "detail_link": "", "provider": "beopmang"},
                {"law_name": "학교안전사고 예방 및 보상에 관한 법률", "law_id": "law-1", "mst": "", "law_type": "법률", "detail_link": "", "provider": "beopmang"},
            ],
        ):
            resolved = law_api.resolve_law_by_name("학교안전사고 예방 및 보상에 관한 법률")

        self.assertEqual(resolved["law_id"], "law-1")

    def test_rank_search_results_prefers_exact_hint_law_over_subordinate_rule(self):
        profile = build_query_profile("쉬는시간에 학생이 다쳤습니다. 교사인 제 책임인가요?")
        results = [
            {
                "law_name": "학교안전사고 예방 및 보상에 관한 법률 시행규칙",
                "law_id": "010520",
                "law_type": "교육부령",
            },
            {
                "law_name": "학교안전사고 예방 및 보상에 관한 법률",
                "law_id": "010380",
                "law_type": "법률",
            },
            {
                "law_name": "상법",
                "law_id": "001702",
                "law_type": "법률",
            },
        ]

        ranked = law_api.rank_search_results(results, profile)

        self.assertEqual(ranked[0]["law_name"], "학교안전사고 예방 및 보상에 관한 법률")


@override_settings(
    TEACHER_LAW_ENABLED=True,
    TEACHER_LAW_FAQ_CACHE_TTL_SECONDS=43200,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "teacher-law-tests"}},
)
class TeacherLawCachingTests(TestCase):
    def tearDown(self):
        cache.clear()

    def test_quick_question_uses_cache_on_second_request(self):
        preset = get_quick_question_presets()[0]
        citation = {
            "citation_id": "law-1",
            "source_type": "law",
            "title": "개인정보 보호법",
            "law_name": "개인정보 보호법",
            "law_id": "123",
            "mst": "999",
            "reference_label": "제15조",
            "article_label": "제15조",
            "case_number": "",
            "quote": "개인정보 처리와 동의에 관한 내용",
            "source_url": "",
            "provider": "beopmang",
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
            patch(
                "teacher_law.services.chat.resolve_law_by_name",
                side_effect=[
                    {"law_name": "개인정보 보호법", "law_id": "123", "mst": "999", "detail_link": citation["source_url"], "provider": "beopmang"},
                    {"law_name": "초ㆍ중등교육법", "law_id": "456", "mst": "", "detail_link": "", "provider": "beopmang"},
                ],
            ) as resolve_mock,
            patch("teacher_law.services.chat.get_law_details", return_value={"law_name": citation["law_name"], "law_id": "123", "mst": "999", "detail_link": citation["source_url"], "articles": []}),
            patch("teacher_law.services.chat.select_relevant_citations", return_value=[citation]),
            patch("teacher_law.services.chat.search_cases", return_value=[]),
            patch("teacher_law.services.chat.generate_legal_answer", return_value=llm_answer),
        ):
            first = answer_legal_question(
                question=preset["question"],
                incident_type=preset["incident_type"],
                legal_goal=preset["legal_goal"],
                counterpart=preset["counterpart"],
                scene=preset["scene"],
            )
            second = answer_legal_question(
                question=preset["question"],
                incident_type=preset["incident_type"],
                legal_goal=preset["legal_goal"],
                counterpart=preset["counterpart"],
                scene=preset["scene"],
            )

        self.assertFalse(first["audit"]["cache_hit"])
        self.assertTrue(second["audit"]["cache_hit"])
        self.assertEqual(resolve_mock.call_count, 2)

    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    @patch.dict("os.environ", {}, clear=True)
    def test_answer_question_works_without_law_api_oc_when_provider_is_beopmang(self):
        citation = {
            "citation_id": "law-1",
            "source_type": "law",
            "title": "민법",
            "law_name": "민법",
            "law_id": "001706",
            "mst": "",
            "reference_label": "제750조",
            "article_label": "제750조",
            "case_number": "",
            "quote": "고의 또는 과실로 인한 손해배상 책임이 있다.",
            "source_url": "",
            "provider": "beopmang",
            "fetched_at": "2026-04-05T00:00:00+09:00",
        }
        llm_answer = {
            "summary": "민법상 손해배상 책임 기준을 먼저 확인해야 합니다.",
            "action_items": ["사실관계를 기록합니다."],
            "citations": ["law-1"],
            "risk_level": "medium",
            "needs_human_help": False,
            "disclaimer": "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다.",
            "scope_supported": True,
        }

        with (
            patch("teacher_law.services.chat.is_llm_configured", return_value=True),
            patch(
                "teacher_law.services.chat.resolve_law_by_name",
                side_effect=[
                    {"law_name": "개인정보 보호법", "law_id": "001111", "mst": "", "detail_link": "", "provider": "beopmang"},
                    {"law_name": "초ㆍ중등교육법", "law_id": "001222", "mst": "", "detail_link": "", "provider": "beopmang"},
                ],
            ),
            patch("teacher_law.services.chat.get_law_details", return_value={"law_name": "민법", "law_id": "001706", "mst": "", "detail_link": "", "provider": "beopmang", "articles": []}) as detail_mock,
            patch("teacher_law.services.chat.select_relevant_citations", return_value=[citation]),
            patch("teacher_law.services.chat.generate_legal_answer", return_value=llm_answer),
        ):
            result = answer_legal_question(
                question="학생 사진을 올리려면 동의가 필요한가요?",
                incident_type="privacy_photo",
                legal_goal="posting_allowed",
                counterpart="student",
            )

        self.assertEqual(result["payload"]["summary"], llm_answer["summary"])
        self.assertEqual(result["audit"]["selected_laws_json"][0]["provider"], "beopmang")
        self.assertTrue(detail_mock.call_args.kwargs["query_hint"])

    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    @patch.dict("os.environ", {}, clear=True)
    def test_answer_question_includes_case_citations_as_secondary_evidence(self):
        law_citation = {
            "citation_id": "law-1",
            "source_type": "law",
            "title": "학교안전사고 예방 및 보상에 관한 법률",
            "law_name": "학교안전사고 예방 및 보상에 관한 법률",
            "law_id": "009620",
            "mst": "",
            "reference_label": "제2조",
            "article_label": "제2조",
            "case_number": "",
            "quote": "학교안전사고의 정의를 정한다.",
            "source_url": "",
            "provider": "beopmang",
            "fetched_at": "2026-04-05T00:00:00+09:00",
        }
        case_citation = {
            "citation_id": "case-1",
            "source_type": "case",
            "title": "학교안전사고 손해배상",
            "law_name": "학교안전사고 손해배상",
            "law_id": "009620",
            "mst": "",
            "reference_label": "2024다12345",
            "article_label": "2024다12345",
            "case_number": "2024다12345",
            "quote": "보호의무 위반 여부를 구체적 사정에 따라 판단했다.",
            "source_url": "",
            "provider": "beopmang",
            "fetched_at": "2026-04-05T00:00:00+09:00",
        }
        llm_answer = {
            "summary": "학교안전사고 법령과 관련 판례를 함께 확인해야 합니다.",
            "action_items": ["사고 경위를 바로 기록합니다."],
            "citations": ["law-1", "case-1"],
            "risk_level": "medium",
            "needs_human_help": False,
            "disclaimer": "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다.",
            "scope_supported": True,
        }

        with (
            patch("teacher_law.services.chat.is_llm_configured", return_value=True),
            patch(
                "teacher_law.services.chat.resolve_law_by_name",
                side_effect=[
                    {"law_name": law_citation["law_name"], "law_id": "009620", "mst": "", "detail_link": "", "provider": "beopmang"},
                    {"law_name": "민법", "law_id": "001706", "mst": "", "detail_link": "", "provider": "beopmang"},
                    {"law_name": "초ㆍ중등교육법", "law_id": "001901", "mst": "", "detail_link": "", "provider": "beopmang"},
                ],
            ),
            patch("teacher_law.services.chat.get_law_details", return_value={"law_name": law_citation["law_name"], "law_id": "009620", "mst": "", "detail_link": "", "provider": "beopmang", "articles": [], "related_cases": []}),
            patch("teacher_law.services.chat.select_relevant_citations", return_value=[law_citation]),
            patch("teacher_law.services.chat.search_cases", return_value=[{"case_id": "case-1", "title": case_citation["title"], "case_number": case_citation["case_number"], "quote": case_citation["quote"], "provider": "beopmang"}]),
            patch("teacher_law.services.chat.select_relevant_case_citations", return_value=[case_citation]),
            patch("teacher_law.services.chat.generate_legal_answer", return_value=llm_answer),
        ):
            result = answer_legal_question(
                question="쉬는시간에 학생이 다쳤는데 교사 책임이 있나요?",
                incident_type="school_safety",
                legal_goal="teacher_liability",
                scene="break_time",
            )

        self.assertEqual(result["payload"]["citations"][0]["source_type"], "law")
        self.assertEqual(result["payload"]["citations"][1]["source_type"], "case")
        self.assertTrue(any(item["source_type"] == "case" for item in result["audit"]["selected_laws_json"]))

    @override_settings(TEACHER_LAW_PROVIDER="beopmang")
    @patch.dict("os.environ", {}, clear=True)
    def test_answer_question_clarifies_when_allowlist_has_no_relevant_articles(self):
        with (
            patch("teacher_law.services.chat.is_llm_configured", return_value=True),
            patch(
                "teacher_law.services.chat.resolve_law_by_name",
                side_effect=[
                    {"law_name": "학교안전사고 예방 및 보상에 관한 법률", "law_id": "010380", "mst": "", "detail_link": "", "provider": "beopmang"},
                    {"law_name": "민법", "law_id": "001706", "mst": "", "detail_link": "", "provider": "beopmang"},
                    {"law_name": "초ㆍ중등교육법", "law_id": "001901", "mst": "", "detail_link": "", "provider": "beopmang"},
                ],
            ),
            patch("teacher_law.services.chat.get_law_details", return_value={"law_name": "학교안전사고 예방 및 보상에 관한 법률", "law_id": "010380", "mst": "", "detail_link": "", "provider": "beopmang", "articles": []}),
            patch("teacher_law.services.chat.select_relevant_citations", return_value=[]),
            patch("teacher_law.services.chat.generate_legal_answer") as llm_mock,
        ):
            result = answer_legal_question(
                question="쉬는시간에 학생이 다쳤습니다. 교사인 제 책임인가요?",
                incident_type="school_safety",
                legal_goal="teacher_liability",
                scene="break_time",
            )

        self.assertEqual(result["status"], "clarify")
        self.assertTrue(result["payload"]["answer_held"])
        self.assertIn("책임 판단", result["payload"]["summary"])
        llm_mock.assert_not_called()
