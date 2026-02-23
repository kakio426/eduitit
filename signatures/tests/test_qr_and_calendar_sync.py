from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarEvent
from classcalendar.models import CalendarIntegrationSetting
from core.models import UserProfile
from signatures.models import TrainingSession
from signatures.views import CALENDAR_INTEGRATION_SOURCE


User = get_user_model()


class SignatureShareQrTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sign_t1",
            password="pw12345",
            email="sign_t1@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "sign_t1", "role": "school"},
        )
        self.client.force_login(self.user)
        self.session = TrainingSession.objects.create(
            title="전체 교원 연수",
            instructor="강사A",
            datetime=timezone.now() + timedelta(days=1),
            location="시청각실",
            created_by=self.user,
        )

    def test_detail_includes_share_qr_context(self):
        url = reverse("signatures:detail", kwargs={"uuid": self.session.uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("share_link", response.context)
        self.assertIn("share_qr_data_url", response.context)
        self.assertTrue(response.context["share_link"].endswith(f"/signatures/sign/{self.session.uuid}/"))
        self.assertTrue(response.context["share_qr_data_url"].startswith("data:image/png;base64,"))
        self.assertContains(response, "프로젝터용 참여 QR")


class SignatureCalendarSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sign_t2",
            password="pw12345",
            email="sign_t2@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "sign_t2", "role": "school"},
        )
        self.client.force_login(self.user)

    def test_create_session_creates_calendar_event(self):
        session_dt = timezone.localtime(timezone.now() + timedelta(days=2)).replace(minute=0, second=0, microsecond=0)
        create_url = reverse("signatures:create")
        response = self.client.post(
            create_url,
            {
                "title": "서명 연동 테스트",
                "print_title": "",
                "instructor": "강사B",
                "datetime": session_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "강당",
                "description": "",
                "expected_count": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)

        session = TrainingSession.objects.get(title="서명 연동 테스트", created_by=self.user)
        calendar_event = CalendarEvent.objects.get(
            author=self.user,
            integration_source=CALENDAR_INTEGRATION_SOURCE,
            integration_key=f"signatures:{session.uuid}",
        )
        self.assertIn("[서명 연수]", calendar_event.title)
        self.assertIn("서명 연동 테스트", calendar_event.title)
        self.assertTrue(calendar_event.is_locked)

    def test_edit_and_delete_session_sync_calendar_event(self):
        original_dt = timezone.now() + timedelta(days=3)
        session = TrainingSession.objects.create(
            title="초기 연수",
            instructor="강사C",
            datetime=original_dt,
            location="1강의실",
            created_by=self.user,
            is_active=True,
        )

        CalendarEvent.objects.create(
            title="[서명 연수] 초기 연수",
            author=self.user,
            start_time=timezone.localtime(original_dt),
            end_time=timezone.localtime(original_dt) + timedelta(minutes=60),
            is_all_day=False,
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            source=CalendarEvent.SOURCE_LOCAL,
            integration_source=CALENDAR_INTEGRATION_SOURCE,
            integration_key=f"signatures:{session.uuid}",
            is_locked=True,
        )

        updated_dt = timezone.localtime(timezone.now() + timedelta(days=5)).replace(minute=30, second=0, microsecond=0)
        edit_url = reverse("signatures:edit", kwargs={"uuid": session.uuid})
        edit_response = self.client.post(
            edit_url,
            {
                "title": "수정 연수",
                "print_title": "",
                "instructor": "강사C",
                "datetime": updated_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "2강의실",
                "description": "",
                "expected_count": "",
                "is_active": "on",
            },
        )
        self.assertEqual(edit_response.status_code, 302)

        calendar_event = CalendarEvent.objects.get(
            author=self.user,
            integration_source=CALENDAR_INTEGRATION_SOURCE,
            integration_key=f"signatures:{session.uuid}",
        )
        self.assertIn("수정 연수", calendar_event.title)

        delete_url = reverse("signatures:delete", kwargs={"uuid": session.uuid})
        delete_response = self.client.post(delete_url)
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(
            CalendarEvent.objects.filter(
                author=self.user,
                integration_source=CALENDAR_INTEGRATION_SOURCE,
                integration_key=f"signatures:{session.uuid}",
            ).exists()
        )

    def test_create_session_skips_calendar_sync_when_signatures_integration_disabled(self):
        CalendarIntegrationSetting.objects.update_or_create(
            user=self.user,
            defaults={"signatures_training_enabled": False},
        )
        session_dt = timezone.localtime(timezone.now() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
        response = self.client.post(
            reverse("signatures:create"),
            {
                "title": "연동 OFF 테스트",
                "print_title": "",
                "instructor": "강사D",
                "datetime": session_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "교실",
                "description": "",
                "expected_count": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        session = TrainingSession.objects.get(title="연동 OFF 테스트", created_by=self.user)
        self.assertFalse(
            CalendarEvent.objects.filter(
                author=self.user,
                integration_source=CALENDAR_INTEGRATION_SOURCE,
                integration_key=f"signatures:{session.uuid}",
            ).exists()
        )
