import os
from datetime import datetime, timedelta
from unittest.mock import patch

from allauth.socialaccount.models import SocialAccount
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
from classcalendar.models import CalendarEvent, CalendarIntegrationSetting, CalendarMessageCapture, CalendarTask
from collect.models import CollectionRequest, Submission
from consent.models import SignatureDocument, SignatureRecipient, SignatureRequest
from reservations.models import Reservation, School, SchoolConfig, SpecialRoom
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
        profile = self.user.userprofile
        profile.nickname = "캘린더쌤"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client = Client()
        self.client.force_login(self.user)
        self.school = School.objects.create(
            name="테스트학교",
            slug="calendar-hub-school",
            owner=self.user,
        )
        SchoolConfig.objects.create(school=self.school)
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
        deadline = timezone.make_aware(
            datetime.combine(timezone.localdate(), datetime.min.time()).replace(hour=18, minute=0),
            timezone.get_current_timezone(),
        )
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

        self.assertIn(hub_map["collect"]["status_label"], {"오늘 마감", "마감 지남"})
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
        self.assertEqual(message_item["message_capture_id"], str(capture.id))
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

    def test_center_view_does_not_render_external_access_card(self):
        response = self.client.get(reverse("classcalendar:center"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Eduitit API 키 / iCal 주소")
        self.assertNotContains(response, "data-classcalendar-external-access")

    def test_external_ical_feed_requires_valid_api_key(self):
        with patch.dict(os.environ, {"EDUITIT_API_KEY": "test-fixed-key"}, clear=False):
            response = Client().get(reverse("classcalendar:external_ical_feed"))

        self.assertEqual(response.status_code, 401)
        self.assertIn("유효한 Eduitit API 키", response.content.decode("utf-8"))

    def test_external_ical_feed_includes_only_user694_naver_calendar_and_hub_items(self):
        now = timezone.now()
        owner = User.objects.create_user(
            username="user694",
            password="pw12345",
            email="user694@example.com",
        )
        owner_profile = owner.userprofile
        owner_profile.nickname = "관리자"
        owner_profile.role = "school"
        owner_profile.save(update_fields=["nickname", "role"])
        SocialAccount.objects.create(user=owner, provider="naver", uid="naver-user694")

        CalendarEvent.objects.create(
            title="학급 회의",
            author=owner,
            start_time=now + timedelta(days=1, hours=1),
            end_time=now + timedelta(days=1, hours=2),
            is_all_day=False,
            source=CalendarEvent.SOURCE_LOCAL,
            visibility=CalendarEvent.VISIBILITY_TEACHER,
        )
        CalendarTask.objects.create(
            title="할 일 항목",
            author=owner,
            due_at=now + timedelta(days=2),
            has_time=False,
        )
        CollectionRequest.objects.create(
            creator=owner,
            title="가정통신문 회신",
            deadline=now + timedelta(days=3),
        )
        CollectionRequest.objects.create(
            creator=self.user,
            title="다른 교사 수합",
            deadline=now + timedelta(days=2),
        )
        CalendarEvent.objects.create(
            title="다른 교사 일정",
            author=self.user,
            start_time=now + timedelta(days=4, hours=1),
            end_time=now + timedelta(days=4, hours=2),
            is_all_day=False,
            source=CalendarEvent.SOURCE_LOCAL,
            visibility=CalendarEvent.VISIBILITY_TEACHER,
        )

        with patch.dict(os.environ, {"EDUITIT_API_KEY": "test-fixed-key"}, clear=False):
            response = Client().get(
                reverse("classcalendar:external_ical_feed"),
                {"api_key": "test-fixed-key"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/calendar", response["Content-Type"])
        content = response.content.decode("utf-8")
        self.assertIn("BEGIN:VCALENDAR", content)
        self.assertIn("SUMMARY:학급 회의", content)
        self.assertIn("SUMMARY:가정통신문 회신", content)
        self.assertNotIn("SUMMARY:할 일 항목", content)
        self.assertNotIn("SUMMARY:다른 교사 일정", content)
        self.assertNotIn("SUMMARY:다른 교사 수합", content)
