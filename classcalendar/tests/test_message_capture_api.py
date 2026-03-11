import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import (
    CalendarEvent,
    CalendarEventAttachment,
    CalendarMessageCapture,
    CalendarMessageCaptureCandidate,
)
from core.models import UserProfile
from sheetbook.models import SheetTab, Sheetbook

User = get_user_model()


@override_settings(
    FEATURE_MESSAGE_CAPTURE_ENABLED=True,
    FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USERNAMES="capture_teacher",
    FEATURE_MESSAGE_CAPTURE_ITEM_TYPES=True,
)
class MessageCaptureApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="capture_teacher",
            password="pw12345",
            email="capture_teacher@example.com",
        )
        self.client = Client()
        self.client.force_login(self.user)
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "메시지교사"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.parse_url = reverse("classcalendar:api_message_capture_parse")
        self.archive_url = reverse("classcalendar:api_message_capture_archive")

    def _commit(self, capture_id, payload):
        return self.client.post(
            reverse("classcalendar:api_message_capture_commit", kwargs={"capture_id": str(capture_id)}),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _archive_list(self, *, query="", filter_value="all", page=1):
        params = {"page": page}
        if query:
            params["query"] = query
        if filter_value:
            params["filter"] = filter_value
        return self.client.get(self.archive_url, data=params)

    def _archive_detail(self, capture_id):
        return self.client.get(
            reverse("classcalendar:api_message_capture_archive_detail", kwargs={"capture_id": str(capture_id)})
        )

    def _build_selected_candidates(self, parse_payload):
        selected = []
        for candidate in parse_payload.get("candidates", []):
            selected.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "selected": not candidate.get("already_saved", False),
                    "title": candidate.get("title") or "",
                    "start_time": candidate.get("start_time") or "",
                    "end_time": candidate.get("end_time") or "",
                    "is_all_day": bool(candidate.get("is_all_day")),
                    "summary": candidate.get("summary") or "",
                }
            )
        return selected

    def _create_archive_capture(
        self,
        *,
        user=None,
        raw_text,
        parse_status=CalendarMessageCapture.ParseStatus.PARSED,
        summary_text="",
        with_candidate=False,
        saved=False,
        candidate_title="테스트 일정",
    ):
        owner = user or self.user
        capture_index = CalendarMessageCapture.objects.count() + 1
        capture = CalendarMessageCapture.objects.create(
            author=owner,
            raw_text=raw_text,
            normalized_text=raw_text,
            parse_status=parse_status,
            idempotency_key=f"archive-capture-{capture_index}",
            content_cache_key=f"archive-cache-{capture_index}",
            parse_payload={"summary_text": summary_text} if summary_text else {},
        )
        if with_candidate:
            start_time = timezone.now().replace(second=0, microsecond=0)
            end_time = start_time + timedelta(hours=1)
            committed_event = None
            commit_status = CalendarMessageCaptureCandidate.CommitStatus.PENDING
            if saved:
                committed_event = CalendarEvent.objects.create(
                    author=owner,
                    title=candidate_title,
                    start_time=start_time,
                    end_time=end_time,
                    is_all_day=False,
                    color="indigo",
                )
                commit_status = CalendarMessageCaptureCandidate.CommitStatus.SAVED
            CalendarMessageCaptureCandidate.objects.create(
                capture=capture,
                sort_order=0,
                candidate_kind=CalendarMessageCaptureCandidate.CandidateKind.EVENT,
                title=candidate_title,
                summary="일정 요약",
                start_time=start_time,
                end_time=end_time,
                is_all_day=False,
                committed_event=committed_event,
                commit_status=commit_status,
            )
        return capture

    def test_parse_returns_candidates_and_reuses_same_content_cache(self):
        first_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시\n12일(목)까지 자료 제출 부탁드립니다.",
                "source_hint": "kakao",
                "idempotency_key": "capture-multi-1",
            },
        )
        self.assertEqual(first_response.status_code, 201)
        first_payload = first_response.json()
        self.assertEqual(first_payload.get("summary_text"), "찾은 일정 2개")
        self.assertEqual(len(first_payload.get("candidates") or []), 2)
        self.assertEqual(first_payload["candidates"][0]["kind"], "deadline")
        self.assertEqual(first_payload["candidates"][1]["kind"], "event")

        second_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시\n12일(목)까지 자료 제출 부탁드립니다.",
                "source_hint": "kakao",
                "idempotency_key": "capture-multi-2",
            },
        )
        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.json()
        self.assertTrue(second_payload.get("reused"))
        self.assertEqual(second_payload.get("capture_id"), first_payload.get("capture_id"))

    def test_parse_uses_idempotency_key_reuse(self):
        first_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시",
                "idempotency_key": "capture-multi-idempotent",
            },
        )
        self.assertEqual(first_response.status_code, 201)

        second_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "다른 텍스트",
                "idempotency_key": "capture-multi-idempotent",
            },
        )
        self.assertEqual(second_response.status_code, 200)
        self.assertTrue(second_response.json().get("reused"))
        self.assertEqual(second_response.json().get("capture_id"), first_response.json().get("capture_id"))

    def test_parse_stores_candidates_and_filters_greeting_title(self):
        response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "선생님 안녕하세요.\n3월 19일 학부모총회 실시\n12일(목)까지 연수물 수정 부탁드립니다.",
                "idempotency_key": "capture-multi-greeting",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        titles = [candidate.get("title") for candidate in payload.get("candidates", [])]
        self.assertEqual(len(titles), 2)
        self.assertTrue(all("선생님 안녕하세요" not in title for title in titles))
        capture = CalendarMessageCapture.objects.get(id=payload["capture_id"])
        self.assertEqual(capture.candidates.count(), 2)

    @patch("classcalendar.views.refine_message_capture_candidates")
    def test_parse_can_apply_deepseek_refinement_when_candidates_are_multiple(self, mock_refine):
        mock_refine.return_value = [
            {
                "kind": "deadline",
                "title": "연수물 수정 마감",
                "summary": "학부모총회 전에 연수물을 수정해 주세요.",
                "is_recommended": True,
                "evidence_text": "12일(목)까지 연수물 수정 부탁드립니다.",
            },
            {
                "kind": "event",
                "title": "학부모총회",
                "summary": "학부모총회가 실시됩니다.",
                "is_recommended": True,
                "evidence_text": "3월 19일 학부모총회 실시",
            },
        ]
        response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시\n12일(목)까지 연수물 수정 부탁드립니다.",
                "idempotency_key": "capture-multi-llm",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload.get("llm_used"))
        self.assertEqual(payload["candidates"][0]["title"], "연수물 수정 마감")
        capture = CalendarMessageCapture.objects.get(id=payload["capture_id"])
        self.assertTrue(capture.llm_used)

    @override_settings(FEATURE_MESSAGE_CAPTURE_CLASSIFIER_ASSIST=True)
    @patch("classcalendar.views.predict_message_capture_item_type")
    def test_classifier_assist_does_not_override_strong_deadline_candidate(self, mock_predict):
        mock_predict.return_value = {
            "label": "event",
            "scores": {"event": 0.95, "task": 0.04, "ignore": 0.01},
            "confidence": 0.95,
        }
        response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시\n12일(목)까지 연수물 수정 부탁드립니다.",
                "idempotency_key": "capture-multi-classifier",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload.get("predicted_item_type"), "task")
        capture = CalendarMessageCapture.objects.get(id=payload["capture_id"])
        self.assertEqual(capture.decision_source, CalendarMessageCapture.DecisionSource.RULE)

    def test_commit_saves_multiple_candidates_and_copies_attachments(self):
        upload = SimpleUploadedFile("memo.txt", b"memo file", content_type="text/plain")
        parse_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시\n12일(목)까지 연수물 수정 부탁드립니다.",
                "idempotency_key": "capture-multi-commit",
                "files": upload,
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        parse_payload = parse_response.json()
        capture_id = parse_payload["capture_id"]

        commit_response = self._commit(
            capture_id,
            {
                "selected_candidates": self._build_selected_candidates(parse_payload),
                "selected_attachment_ids": [item["id"] for item in parse_payload.get("attachments", [])],
            },
        )
        self.assertEqual(commit_response.status_code, 201)
        payload = commit_response.json()
        self.assertEqual(len(payload.get("created_events") or []), 2)
        self.assertEqual(payload.get("saved_count"), 2)
        self.assertIn("저장했어요", payload.get("message") or "")

        capture = CalendarMessageCapture.objects.get(id=capture_id)
        candidates = list(capture.candidates.order_by("sort_order"))
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(candidate.commit_status == CalendarMessageCaptureCandidate.CommitStatus.SAVED for candidate in candidates))
        self.assertTrue(all(candidate.committed_event_id for candidate in candidates))
        for candidate in candidates:
            self.assertEqual(CalendarEventAttachment.objects.filter(event_id=candidate.committed_event_id).count(), 1)

    def test_commit_reuses_already_saved_candidates_without_duplication(self):
        parse_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시\n12일(목)까지 연수물 수정 부탁드립니다.",
                "idempotency_key": "capture-multi-recommit",
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        parse_payload = parse_response.json()
        capture_id = parse_payload["capture_id"]
        commit_payload = {"selected_candidates": self._build_selected_candidates(parse_payload)}

        first_commit = self._commit(capture_id, commit_payload)
        self.assertEqual(first_commit.status_code, 201)
        event_count_after_first = CalendarEvent.objects.count()

        second_commit = self._commit(capture_id, commit_payload)
        self.assertEqual(second_commit.status_code, 201)
        self.assertEqual(CalendarEvent.objects.count(), event_count_after_first)
        self.assertEqual(len(second_commit.json().get("created_events") or []), 0)
        self.assertEqual(len(second_commit.json().get("reused_events") or []), 2)

    def test_commit_can_link_saved_events_back_to_sheetbook_context(self):
        sheetbook = Sheetbook.objects.create(owner=self.user, title="2026 3-1 교무수첩")
        calendar_tab = SheetTab.objects.create(
            sheetbook=sheetbook,
            name="달력",
            tab_type=SheetTab.TYPE_CALENDAR,
            sort_order=1,
        )
        parse_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시\n12일(목)까지 연수물 수정 부탁드립니다.",
                "idempotency_key": "capture-multi-source-meta",
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        parse_payload = parse_response.json()

        commit_response = self._commit(
            parse_payload["capture_id"],
            {
                "selected_candidates": self._build_selected_candidates(parse_payload),
                "source_sheetbook_id": sheetbook.id,
                "source_tab_id": calendar_tab.id,
            },
        )
        self.assertEqual(commit_response.status_code, 201)
        created_event_ids = [item["id"] for item in commit_response.json().get("created_events", [])]

        events_response = self.client.get(reverse("classcalendar:api_events"))
        self.assertEqual(events_response.status_code, 200)
        events = events_response.json().get("events", [])
        saved_events = [item for item in events if item.get("id") in created_event_ids]
        self.assertEqual(len(saved_events), 2)
        self.assertTrue(all(item.get("source_sheetbook_id") == sheetbook.id for item in saved_events))
        self.assertTrue(all(item.get("source_tab_id") == calendar_tab.id for item in saved_events))

    def test_parse_rejects_too_large_file(self):
        upload = SimpleUploadedFile("notice.txt", b"0123456789ABCDEF", content_type="text/plain")
        with patch("classcalendar.views.MESSAGE_CAPTURE_MAX_FILE_BYTES", 8):
            response = self.client.post(
                self.parse_url,
                data={
                    "raw_text": "3월 19일 학부모총회 실시",
                    "idempotency_key": "capture-multi-large-file",
                    "files": upload,
                },
            )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json().get("code"), "file_too_large")

    @override_settings(FEATURE_MESSAGE_CAPTURE_ENABLED=False)
    def test_parse_returns_feature_disabled_when_flag_off(self):
        response = self.client.post(
            self.parse_url,
            data={"raw_text": "3월 19일 학부모총회 실시"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get("code"), "feature_disabled")

    def test_archive_list_reuses_same_capture_for_same_message_content(self):
        first_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시\n12일(목)까지 자료 제출 부탁드립니다.",
                "source_hint": "kakao",
                "idempotency_key": "archive-reuse-1",
            },
        )
        self.assertEqual(first_response.status_code, 201)
        first_payload = first_response.json()

        second_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시\n12일(목)까지 자료 제출 부탁드립니다.",
                "source_hint": "kakao",
                "idempotency_key": "archive-reuse-2",
            },
        )
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json().get("capture_id"), first_payload.get("capture_id"))

        archive_response = self._archive_list()
        self.assertEqual(archive_response.status_code, 200)
        archive_payload = archive_response.json()
        self.assertEqual(archive_payload.get("counts", {}).get("all"), 1)
        self.assertEqual(len(archive_payload.get("items") or []), 1)
        self.assertEqual(archive_payload["items"][0]["capture_id"], first_payload["capture_id"])

    def test_archive_detail_shows_candidates_and_saved_events_for_committed_capture(self):
        parse_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 19일 학부모총회 실시\n12일(목)까지 연수물 수정 부탁드립니다.",
                "idempotency_key": "archive-detail-commit",
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        parse_payload = parse_response.json()

        commit_response = self._commit(
            parse_payload["capture_id"],
            {"selected_candidates": self._build_selected_candidates(parse_payload)},
        )
        self.assertEqual(commit_response.status_code, 201)

        detail_response = self._archive_detail(parse_payload["capture_id"])
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        self.assertEqual(len(detail_payload.get("candidates") or []), 2)
        self.assertEqual(len(detail_payload.get("saved_events") or []), 2)
        self.assertTrue(all(candidate.get("already_saved") for candidate in detail_payload.get("candidates") or []))
        self.assertTrue(detail_payload.get("created_at"))

    def test_archive_list_and_detail_show_failed_message_without_candidates(self):
        capture = self._create_archive_capture(
            raw_text="안내만 전달드립니다. 자세한 일정은 추후 공지합니다.",
            parse_status=CalendarMessageCapture.ParseStatus.FAILED,
            summary_text="일정을 찾지 못했어요",
            with_candidate=False,
        )

        archive_response = self._archive_list(filter_value="failed")
        self.assertEqual(archive_response.status_code, 200)
        items = archive_response.json().get("items") or []
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["capture_id"], str(capture.id))
        self.assertEqual(items[0]["archive_status"], "failed")

        detail_response = self._archive_detail(capture.id)
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload.get("parse_status"), CalendarMessageCapture.ParseStatus.FAILED)
        self.assertEqual(detail_payload.get("candidates"), [])
        self.assertEqual(detail_payload.get("saved_events"), [])

    def test_archive_filters_saved_pending_review_and_failed(self):
        saved_capture = self._create_archive_capture(
            raw_text="3월 12일 저장된 일정",
            summary_text="저장된 일정",
            with_candidate=True,
            saved=True,
            candidate_title="저장 완료 일정",
        )
        pending_capture = self._create_archive_capture(
            raw_text="3월 13일 아직 저장하지 않은 일정",
            summary_text="미저장 일정",
            with_candidate=True,
            saved=False,
            candidate_title="미저장 일정",
        )
        review_capture = self._create_archive_capture(
            raw_text="3월 중 일정 확인 부탁",
            parse_status=CalendarMessageCapture.ParseStatus.NEEDS_REVIEW,
            summary_text="확인 필요 일정",
            with_candidate=True,
            saved=False,
            candidate_title="확인 필요 일정",
        )
        failed_capture = self._create_archive_capture(
            raw_text="참고만 부탁드립니다.",
            parse_status=CalendarMessageCapture.ParseStatus.FAILED,
            summary_text="일정 못 찾음",
            with_candidate=False,
        )

        all_response = self._archive_list()
        self.assertEqual(all_response.status_code, 200)
        counts = all_response.json().get("counts") or {}
        self.assertEqual(counts.get("all"), 4)
        self.assertEqual(counts.get("saved"), 1)
        self.assertEqual(counts.get("pending"), 1)
        self.assertEqual(counts.get("needs_review"), 1)
        self.assertEqual(counts.get("failed"), 1)

        saved_ids = {item["capture_id"] for item in (self._archive_list(filter_value="saved").json().get("items") or [])}
        pending_ids = {item["capture_id"] for item in (self._archive_list(filter_value="pending").json().get("items") or [])}
        review_ids = {item["capture_id"] for item in (self._archive_list(filter_value="needs_review").json().get("items") or [])}
        failed_ids = {item["capture_id"] for item in (self._archive_list(filter_value="failed").json().get("items") or [])}

        self.assertEqual(saved_ids, {str(saved_capture.id)})
        self.assertEqual(pending_ids, {str(pending_capture.id)})
        self.assertEqual(review_ids, {str(review_capture.id)})
        self.assertEqual(failed_ids, {str(failed_capture.id)})

    def test_archive_is_private_to_current_user(self):
        other_user = User.objects.create_user(
            username="another_teacher",
            password="pw12345",
            email="another_teacher@example.com",
        )
        self._create_archive_capture(
            user=other_user,
            raw_text="3월 25일 다른 사용자 일정",
            summary_text="다른 사용자 메시지",
            with_candidate=True,
            saved=False,
            candidate_title="다른 사용자 일정",
        )

        list_response = self._archive_list()
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json().get("counts", {}).get("all"), 0)
        self.assertEqual(list_response.json().get("items"), [])

        foreign_capture = CalendarMessageCapture.objects.filter(author=other_user).first()
        detail_response = self._archive_detail(foreign_capture.id)
        self.assertEqual(detail_response.status_code, 404)

    def test_main_shows_message_capture_entry_for_allowlist_user(self):
        response = self.client.get(reverse("classcalendar:legacy_main"), follow=True)
        self.assertRedirects(response, reverse("classcalendar:main"))
        self.assertContains(response, "openMessageHub($event, 'capture', { resetCapture: true })")
        self.assertContains(response, "메시지")
        self.assertNotContains(response, '@click.prevent="openMessageCaptureModal($event)"')

    @override_settings(FEATURE_MESSAGE_CAPTURE_ENABLED=False)
    def test_main_hides_message_capture_entry_when_feature_off(self):
        response = self.client.get(reverse("classcalendar:legacy_main"), follow=True)
        self.assertRedirects(response, reverse("classcalendar:main"))
        self.assertNotContains(response, "openMessageHub($event, 'capture', { resetCapture: true })")
