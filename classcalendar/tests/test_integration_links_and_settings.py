from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from classcalendar.integrations import (
    SOURCE_COLLECT_DEADLINE,
    SOURCE_CONSENT_EXPIRY,
    SOURCE_SIGNATURES_TRAINING,
)
from classcalendar.models import CalendarEvent, CalendarIntegrationSetting, CalendarMessageCapture
from collect.models import CollectionRequest, Submission
from consent.models import SignatureDocument, SignatureRecipient, SignatureRequest
from reservations.models import Reservation, School, SpecialRoom
from signatures.models import TrainingSession


User = get_user_model()


@override_settings(
    FEATURE_MESSAGE_CAPTURE_ENABLED=True,
)
class IntegrationLinksAndSettingsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cc_link_user",
            password="pw12345",
            email="cc_link_user@example.com",
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.school = School.objects.create(
            name="테스트학교",
            slug="calendar-hub-school",
            owner=self.user,
        )
        self.room = SpecialRoom.objects.create(
            school=self.school,
            name="과학실",
            icon="🔬",
        )

    def _create_locked_event(self, *, source, key, title):
        now = timezone.now()
        return CalendarEvent.objects.create(
            title=title,
            author=self.user,
            start_time=now,
            end_time=now + timedelta(hours=1),
            is_all_day=False,
            source=CalendarEvent.SOURCE_LOCAL,
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            integration_source=source,
            integration_key=key,
            is_locked=True,
        )

    def _create_consent_request(self, *, title="동의서 요청", sent_at=None):
        document = SignatureDocument.objects.create(
            created_by=self.user,
            title="학부모 동의서",
            original_file=SimpleUploadedFile("consent.pdf", b"pdf", content_type="application/pdf"),
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        return SignatureRequest.objects.create(
            document_name_snapshot="consent.pdf",
            created_by=self.user,
            document=document,
            title=title,
            status=SignatureRequest.STATUS_SENT,
            sent_at=sent_at or timezone.now(),
        )

    def _hub_items(self, response):
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "success")
        return payload.get("hub_items") or []

    def test_api_events_includes_direct_hub_links_for_all_integrations(self):
        deadline = timezone.now() + timedelta(hours=4)
        collect_request = CollectionRequest.objects.create(
            creator=self.user,
            title="수합 마감",
            deadline=deadline,
        )
        consent_request = self._create_consent_request(sent_at=timezone.now() - timedelta(days=1))
        reservation = Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            date=timezone.localdate(),
            period=2,
            grade=5,
            class_no=1,
            name="담임",
        )
        session = TrainingSession.objects.create(
            title="서명 연수",
            instructor="강사A",
            datetime=timezone.now() + timedelta(days=1),
            location="시청각실",
            created_by=self.user,
        )

        response = self.client.get(reverse("classcalendar:api_events"))
        hub_map = {
            item["item_kind"]: item
            for item in self._hub_items(response)
            if item.get("item_kind") in {"collect", "consent", "reservation", "signature"}
        }

        self.assertIn(str(collect_request.id), hub_map["collect"]["source_url"])
        self.assertTrue(hub_map["consent"]["source_url"].endswith(f"/consent/{consent_request.request_id}/"))
        self.assertIn(f"reservation={reservation.id}", hub_map["reservation"]["source_url"])
        self.assertTrue(hub_map["signature"]["source_url"].endswith(f"/signatures/{session.uuid}/"))

    def test_api_events_includes_direct_hub_status_and_day_markers(self):
        deadline = timezone.now() + timedelta(hours=2)
        collect_request = CollectionRequest.objects.create(
            creator=self.user,
            title="가정통신문 회신",
            deadline=deadline,
        )
        consent_request = self._create_consent_request(
            title="체험학습 동의서",
            sent_at=timezone.now() - timedelta(days=14),
        )
        SignatureRecipient.objects.create(
            request=consent_request,
            student_name="학생1",
            parent_name="학부모1",
            phone_number="01012341234",
            status=SignatureRecipient.STATUS_PENDING,
        )
        Reservation.objects.create(
            room=self.room,
            created_by=self.user,
            date=timezone.localdate(),
            period=3,
            grade=5,
            class_no=2,
            name="교사",
        )

        response = self.client.get(reverse("classcalendar:api_events"))
        payload = response.json()
        hub_map = {item["item_kind"]: item for item in payload.get("hub_items") or []}
        day_markers = payload.get("day_markers") or {}

        self.assertEqual(hub_map["collect"]["status_label"], "오늘 마감")
        self.assertEqual(hub_map["collect"]["tone"], "warning")
        self.assertEqual(hub_map["consent"]["status_label"], "만료")
        self.assertIn("reservation", day_markers[timezone.localdate().isoformat()]["kinds"])
        self.assertIn("collect", day_markers[timezone.localtime(deadline).date().isoformat()]["kinds"])
        self.assertTrue(hub_map["reservation"]["source_label"])

    def test_api_events_collect_hub_meta_uses_submission_total(self):
        request_item = CollectionRequest.objects.create(
            creator=self.user,
            title="가정통신문 회신",
            deadline=timezone.now() + timedelta(hours=4),
        )
        Submission.objects.create(
            collection_request=request_item,
            contributor_name="김교사",
            submission_type="text",
            text_content="회신 완료",
        )

        response = self.client.get(reverse("classcalendar:api_events"))
        collect_item = next(
            item for item in self._hub_items(response)
            if item.get("item_kind") == "collect" and item.get("title") == "가정통신문 회신"
        )
        self.assertIn("제출 1건", collect_item["meta_text"])

    def test_api_events_excludes_legacy_locked_integration_events_from_native_events(self):
        stale_event = self._create_locked_event(
            source=SOURCE_COLLECT_DEADLINE,
            key="collect:stale",
            title="만료된 연동 일정",
        )
        CollectionRequest.objects.create(
            creator=self.user,
            title="실제 수합",
            deadline=timezone.now() + timedelta(days=1),
        )

        response = self.client.get(reverse("classcalendar:api_events"))
        payload = response.json()

        self.assertFalse(any(item["id"] == str(stale_event.id) for item in payload.get("events") or []))
        self.assertTrue(any(item["item_kind"] == "collect" for item in payload.get("hub_items") or []))

    def test_api_events_marks_linked_message_capture_as_hub_item(self):
        linked_for_at = timezone.make_aware(
            datetime.combine(timezone.localdate() + timedelta(days=1), datetime.min.time()),
            timezone.get_current_timezone(),
        )
        capture = CalendarMessageCapture.objects.create(
            author=self.user,
            raw_text="내일 확인할 메시지",
            extracted_title="내일 확인할 메시지",
            linked_for_at=linked_for_at,
            follow_up_state=CalendarMessageCapture.FollowUpState.PENDING,
        )

        response = self.client.get(reverse("classcalendar:api_events"))
        message_item = next(
            item for item in self._hub_items(response)
            if item.get("item_kind") == "message" and item.get("id") == f"message:{capture.id}"
        )

        self.assertEqual(message_item["status_label"], "처리 예정")
        self.assertIn(f"capture={capture.id}", message_item["source_url"])

    def test_api_integration_settings_disables_and_cleans_up_sources(self):
        self._create_locked_event(
            source=SOURCE_COLLECT_DEADLINE,
            key="collect:legacy-cleanup",
            title="수합 마감",
        )
        self._create_locked_event(
            source=SOURCE_SIGNATURES_TRAINING,
            key="signatures:legacy-cleanup",
            title="서명 연수",
        )
        self._create_locked_event(
            source=SOURCE_CONSENT_EXPIRY,
            key="consent:legacy-cleanup",
            title="동의서 만료",
        )

        response = self.client.post(
            reverse("classcalendar:api_integration_settings"),
            {
                "collect_deadline_enabled": "false",
                "consent_expiry_enabled": "false",
                "reservation_enabled": "true",
                "signatures_training_enabled": "false",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["settings"]["collect_deadline_enabled"])
        self.assertFalse(payload["settings"]["consent_expiry_enabled"])
        self.assertFalse(payload["settings"]["signatures_training_enabled"])

        self.assertFalse(
            CalendarEvent.objects.filter(author=self.user, integration_source=SOURCE_COLLECT_DEADLINE).exists()
        )
        self.assertFalse(
            CalendarEvent.objects.filter(author=self.user, integration_source=SOURCE_CONSENT_EXPIRY).exists()
        )
        self.assertFalse(
            CalendarEvent.objects.filter(author=self.user, integration_source=SOURCE_SIGNATURES_TRAINING).exists()
        )

        setting = CalendarIntegrationSetting.objects.get(user=self.user)
        self.assertFalse(setting.collect_deadline_enabled)
        self.assertFalse(setting.consent_expiry_enabled)
        self.assertFalse(setting.signatures_training_enabled)
