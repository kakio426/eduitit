import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from classcalendar.models import CalendarEvent, CalendarEventAttachment, CalendarMessageCapture, CalendarTask
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

    def _commit(self, capture_id, payload):
        return self.client.post(
            reverse("classcalendar:api_message_capture_commit", kwargs={"capture_id": str(capture_id)}),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_parse_creates_capture_and_supports_idempotency_reuse(self):
        upload = SimpleUploadedFile("notice.txt", b"message capture test", content_type="text/plain")
        first_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "3월 15일 오후 2시 과학 실험실 수업",
                "source_hint": "kakao",
                "idempotency_key": "capture-test-key-1",
                "files": upload,
            },
        )
        self.assertEqual(first_response.status_code, 201)
        first_payload = first_response.json()
        capture_id = first_payload.get("capture_id")
        self.assertTrue(capture_id)
        capture = CalendarMessageCapture.objects.get(id=capture_id)
        self.assertEqual(capture.attachments.count(), 1)

        second_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "같은 요청 재전송",
                "source_hint": "kakao",
                "idempotency_key": "capture-test-key-1",
            },
        )
        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.json()
        self.assertEqual(second_payload.get("capture_id"), capture_id)
        self.assertTrue(second_payload.get("reused"))

    def test_parse_returns_parsed_status_and_item_type_mapping(self):
        response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "과학 실험 안내\n2026-03-15 14:00-15:20 과학실 수업\n준비물: 실험 노트",
                "idempotency_key": "capture-test-key-mapping",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload.get("parse_status"), "parsed")
        self.assertEqual(payload.get("confidence_label"), "high")
        self.assertEqual(payload.get("predicted_item_type"), "event")
        draft = payload.get("draft_event") or {}
        self.assertEqual(draft.get("title"), "과학 실험 안내")
        self.assertFalse(draft.get("needs_confirmation"))
        self.assertEqual(draft.get("priority"), "normal")
        self.assertIn("start_time", draft)
        self.assertIn("end_time", draft)
        self.assertIn("parse_evidence", draft)

    def test_parse_stores_initial_snapshot_for_task(self):
        response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "2026-03-15까지 실험 노트 제출",
                "idempotency_key": "capture-test-key-task-snapshot",
            },
        )
        self.assertEqual(response.status_code, 201)
        capture = CalendarMessageCapture.objects.get(id=response.json()["capture_id"])
        self.assertEqual(capture.predicted_item_type, CalendarMessageCapture.ItemType.TASK)
        self.assertEqual(capture.initial_extract_payload.get("predicted_item_type"), "task")
        self.assertTrue(capture.initial_extract_payload.get("draft_task", {}).get("due_at"))

    def test_parse_returns_needs_review_for_ambiguous_datetime(self):
        response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "학부모 상담\n내일 3시 상담실 방문",
                "idempotency_key": "capture-test-key-ambiguous",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload.get("parse_status"), "needs_review")
        draft = payload.get("draft_event") or {}
        self.assertTrue(draft.get("needs_confirmation"))
        self.assertTrue(any("확인" in warning for warning in payload.get("warnings", [])))

    def test_parse_returns_validation_error_when_input_missing(self):
        response = self.client.post(
            self.parse_url,
            data={"idempotency_key": "capture-test-key-empty"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("code"), "validation_error")

    def test_parse_rejects_unsupported_file_extension(self):
        upload = SimpleUploadedFile("run.exe", b"MZ...", content_type="application/octet-stream")
        response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "2026-03-20 09:00 학급회의",
                "idempotency_key": "capture-test-key-invalid-ext",
                "files": upload,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("code"), "validation_error")

    def test_parse_rejects_too_large_file(self):
        upload = SimpleUploadedFile("notice.txt", b"0123456789ABCDEF", content_type="text/plain")
        with patch("classcalendar.views.MESSAGE_CAPTURE_MAX_FILE_BYTES", 8):
            response = self.client.post(
                self.parse_url,
                data={
                    "raw_text": "2026-03-20 09:00 학급회의",
                    "idempotency_key": "capture-test-key-large-file",
                    "files": upload,
                },
            )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json().get("code"), "file_too_large")

    def test_low_confidence_capture_requires_confirmation_before_commit(self):
        parse_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "준비물 공지\n실험 노트 챙기기",
                "idempotency_key": "capture-test-key-2",
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        capture_id = parse_response.json()["capture_id"]

        base_payload = {
            "confirmed_item_type": "event",
            "title": "실험 노트 준비",
            "todo_summary": "실험 노트 챙기기",
            "start_time": "2026-03-05T09:00",
            "end_time": "2026-03-05T10:00",
            "is_all_day": False,
            "color": "indigo",
            "selected_attachment_ids": [],
        }

        blocked_response = self._commit(
            capture_id,
            {
                **base_payload,
                "confirm_low_confidence": False,
            },
        )
        self.assertEqual(blocked_response.status_code, 422)
        self.assertEqual(blocked_response.json().get("code"), "needs_confirmation")

        commit_response = self._commit(
            capture_id,
            {
                **base_payload,
                "confirm_low_confidence": True,
            },
        )
        self.assertEqual(commit_response.status_code, 201)
        payload = commit_response.json()
        event_id = payload["event"]["id"]
        self.assertTrue(CalendarEvent.objects.filter(id=event_id).exists())

        capture = CalendarMessageCapture.objects.get(id=capture_id)
        self.assertEqual(str(capture.committed_event_id), event_id)
        self.assertIsNone(capture.committed_task_id)
        self.assertIsNotNone(capture.committed_at)

    def test_task_commit_creates_task_and_preserves_original_extracted_values(self):
        parse_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "2026-03-15까지 실험 노트 제출",
                "idempotency_key": "capture-test-key-task-commit",
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        capture_id = parse_response.json()["capture_id"]
        capture_before = CalendarMessageCapture.objects.get(id=capture_id)
        original_extracted_title = capture_before.extracted_title

        commit_response = self._commit(
            capture_id,
            {
                "confirmed_item_type": "task",
                "title": "실험 노트 제출 마감",
                "note": "1교시 시작 전까지 제출",
                "due_at": "2026-03-15T23:59",
                "has_time": False,
                "priority": "high",
                "selected_attachment_ids": [],
                "confirm_low_confidence": True,
            },
        )
        self.assertEqual(commit_response.status_code, 201)
        payload = commit_response.json()
        self.assertEqual(payload.get("item_type"), "task")
        task_id = payload["task"]["id"]
        self.assertTrue(CalendarTask.objects.filter(id=task_id).exists())

        capture = CalendarMessageCapture.objects.get(id=capture_id)
        self.assertEqual(str(capture.committed_task_id), task_id)
        self.assertIsNone(capture.committed_event_id)
        self.assertEqual(capture.extracted_title, original_extracted_title)
        self.assertEqual(capture.final_commit_payload.get("item_type"), "task")
        self.assertIn("item_type", capture.edit_diff_payload.get("field_changes", {}))
        self.assertFalse(capture.edit_diff_payload["field_changes"]["item_type"]["changed"])
        self.assertEqual(capture.edit_diff_payload["field_changes"]["item_type"]["final"], "task")
        self.assertEqual(capture.confirmed_item_type, CalendarMessageCapture.ConfirmedItemType.TASK)

    def test_task_commit_with_attachments_returns_warning(self):
        upload = SimpleUploadedFile("memo.txt", b"memo file", content_type="text/plain")
        parse_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "2026-03-15까지 준비물 확인",
                "idempotency_key": "capture-test-key-task-attachment",
                "files": upload,
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        parse_payload = parse_response.json()
        capture_id = parse_payload["capture_id"]
        selected_attachment_ids = [item["id"] for item in parse_payload.get("attachments", [])]

        commit_response = self._commit(
            capture_id,
            {
                "confirmed_item_type": "task",
                "title": "준비물 확인",
                "note": "첨부는 참고만",
                "due_at": "2026-03-15T23:59",
                "has_time": False,
                "priority": "normal",
                "selected_attachment_ids": selected_attachment_ids,
                "confirm_low_confidence": True,
            },
        )
        self.assertEqual(commit_response.status_code, 201)
        payload = commit_response.json()
        self.assertEqual(payload.get("attachments"), [])
        self.assertTrue(any("첨부파일" in warning for warning in payload.get("warnings", [])))

    def test_commit_returns_duplicate_request_after_first_success(self):
        upload = SimpleUploadedFile("memo.txt", b"memo file", content_type="text/plain")
        parse_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "2026-03-12 10:00-11:00 학부모 상담",
                "idempotency_key": "capture-test-key-3",
                "files": upload,
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        parse_payload = parse_response.json()
        capture_id = parse_payload["capture_id"]
        selected_attachment_ids = [item["id"] for item in parse_payload.get("attachments", [])]

        commit_payload = {
            "confirmed_item_type": "event",
            "title": "학부모 상담",
            "todo_summary": "상담실 준비",
            "start_time": "2026-03-12T10:00",
            "end_time": "2026-03-12T11:00",
            "is_all_day": False,
            "color": "indigo",
            "selected_attachment_ids": selected_attachment_ids,
            "confirm_low_confidence": True,
        }
        first_commit = self._commit(capture_id, commit_payload)
        self.assertEqual(first_commit.status_code, 201)
        created_event_id = first_commit.json()["event"]["id"]
        self.assertEqual(CalendarEventAttachment.objects.filter(event_id=created_event_id).count(), 1)

        second_commit = self._commit(capture_id, commit_payload)
        self.assertEqual(second_commit.status_code, 409)
        self.assertEqual(second_commit.json().get("code"), "duplicate_request")

    def test_api_events_includes_message_capture_attachment_metadata(self):
        upload = SimpleUploadedFile("memo.txt", b"memo file", content_type="text/plain")
        parse_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "2026-03-12 10:00-11:00 학부모 상담",
                "idempotency_key": "capture-test-key-attachments-api",
                "files": upload,
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        parse_payload = parse_response.json()
        capture_id = parse_payload["capture_id"]
        selected_attachment_ids = [item["id"] for item in parse_payload.get("attachments", [])]

        commit_response = self._commit(
            capture_id,
            {
                "confirmed_item_type": "event",
                "title": "학부모 상담",
                "todo_summary": "상담실 준비",
                "start_time": "2026-03-12T10:00",
                "end_time": "2026-03-12T11:00",
                "is_all_day": False,
                "color": "indigo",
                "selected_attachment_ids": selected_attachment_ids,
                "confirm_low_confidence": True,
            },
        )
        self.assertEqual(commit_response.status_code, 201)
        event_id = commit_response.json()["event"]["id"]

        events_response = self.client.get(reverse("classcalendar:api_events"))
        self.assertEqual(events_response.status_code, 200)
        events = events_response.json().get("events", [])
        event_payload = next(item for item in events if item.get("id") == event_id)
        attachments = event_payload.get("attachments") or []
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get("original_name"), "memo.txt")
        self.assertTrue(attachments[0].get("url"))

    def test_api_events_returns_tasks_array(self):
        parse_response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "2026-03-19까지 가정통신문 확인",
                "idempotency_key": "capture-test-key-task-events",
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        capture_id = parse_response.json()["capture_id"]
        commit_response = self._commit(
            capture_id,
            {
                "confirmed_item_type": "task",
                "title": "가정통신문 확인",
                "note": "학생 전달 여부 체크",
                "due_at": "2026-03-19T23:59",
                "has_time": False,
                "priority": "normal",
                "selected_attachment_ids": [],
                "confirm_low_confidence": True,
            },
        )
        self.assertEqual(commit_response.status_code, 201)
        task_id = commit_response.json()["task"]["id"]

        response = self.client.get(reverse("classcalendar:api_events"))
        self.assertEqual(response.status_code, 200)
        tasks = response.json().get("tasks", [])
        task_payload = next(item for item in tasks if item.get("id") == task_id)
        self.assertEqual(task_payload.get("title"), "가정통신문 확인")
        self.assertEqual(task_payload.get("item_type"), "task")

    def test_api_events_expose_sheetbook_source_metadata_for_message_capture_commit(self):
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
                "raw_text": "2026-03-18 09:00-10:00 학급 회의",
                "idempotency_key": "capture-test-key-source-meta",
            },
        )
        self.assertEqual(parse_response.status_code, 201)
        capture_id = parse_response.json()["capture_id"]

        commit_response = self._commit(
            capture_id,
            {
                "confirmed_item_type": "event",
                "title": "학급 회의",
                "todo_summary": "회의 준비",
                "start_time": "2026-03-18T09:00",
                "end_time": "2026-03-18T10:00",
                "is_all_day": False,
                "color": "indigo",
                "selected_attachment_ids": [],
                "confirm_low_confidence": True,
                "source_sheetbook_id": sheetbook.id,
                "source_tab_id": calendar_tab.id,
            },
        )
        self.assertEqual(commit_response.status_code, 201)
        event_id = commit_response.json()["event"]["id"]

        events_response = self.client.get(reverse("classcalendar:api_events"))
        self.assertEqual(events_response.status_code, 200)
        events = events_response.json().get("events", [])
        event_payload = next(item for item in events if item.get("id") == event_id)
        self.assertEqual(event_payload.get("source_sheetbook_id"), sheetbook.id)
        self.assertEqual(event_payload.get("source_sheetbook_title"), sheetbook.title)
        self.assertEqual(event_payload.get("source_tab_id"), calendar_tab.id)
        self.assertEqual(event_payload.get("source_tab_name"), calendar_tab.name)
        self.assertIn(reverse("sheetbook:detail", kwargs={"pk": sheetbook.pk}), event_payload.get("source_detail_url") or "")

    @override_settings(FEATURE_MESSAGE_CAPTURE_CLASSIFIER_SHADOW=True)
    @patch("classcalendar.views.predict_message_capture_item_type")
    def test_classifier_shadow_scores_saved_without_overriding_rule_prediction(self, mock_predict):
        mock_predict.return_value = {
            "label": "task",
            "scores": {"event": 0.1, "task": 0.85, "ignore": 0.05},
            "confidence": 0.85,
        }
        response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "2026-03-20 09:00 학년 회의",
                "idempotency_key": "capture-test-key-shadow",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload.get("predicted_item_type"), "event")
        capture = CalendarMessageCapture.objects.get(id=payload["capture_id"])
        self.assertEqual(capture.decision_source, CalendarMessageCapture.DecisionSource.RULE)
        self.assertIn("task", capture.ml_scores)

    @override_settings(FEATURE_MESSAGE_CAPTURE_CLASSIFIER_ASSIST=True)
    @patch("classcalendar.views.predict_message_capture_item_type")
    def test_classifier_assist_can_adjust_predicted_item_type(self, mock_predict):
        mock_predict.return_value = {
            "label": "task",
            "scores": {"event": 0.1, "task": 0.9, "ignore": 0.0},
            "confidence": 0.9,
        }
        response = self.client.post(
            self.parse_url,
            data={
                "raw_text": "2026-03-20 09:00 학년 회의",
                "idempotency_key": "capture-test-key-assist",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload.get("predicted_item_type"), "task")
        capture = CalendarMessageCapture.objects.get(id=payload["capture_id"])
        self.assertEqual(capture.decision_source, CalendarMessageCapture.DecisionSource.RULE_ML)

    @override_settings(FEATURE_MESSAGE_CAPTURE_ENABLED=False)
    def test_parse_returns_feature_disabled_when_flag_off(self):
        response = self.client.post(
            self.parse_url,
            data={"raw_text": "2026-03-20 09:00 학급회의"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get("code"), "feature_disabled")

    def test_legacy_main_redirects_and_main_shows_message_capture_entry_for_allowlist_user(self):
        response = self.client.get(reverse("classcalendar:legacy_main"), follow=True)
        self.assertRedirects(response, reverse("classcalendar:main"))
        self.assertContains(response, '@click.prevent="openMessageCaptureModal($event)"')
        self.assertContains(response, "메시지 바로 등록")

    def test_legacy_main_redirects_and_main_hides_message_capture_entry_for_non_allowlist_user(self):
        non_allowlist_user = User.objects.create_user(
            username="non_allowlist_teacher",
            password="pw12345",
            email="non_allowlist_teacher@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=non_allowlist_user)
        profile.nickname = "비허용교사"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])

        client = Client()
        client.force_login(non_allowlist_user)
        response = client.get(reverse("classcalendar:legacy_main"), follow=True)
        self.assertRedirects(response, reverse("classcalendar:main"))
        self.assertNotContains(response, '@click.prevent="openMessageCaptureModal($event)"')
