from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarIntegrationSetting
from core.models import UserProfile
from signatures.models import TrainingSession


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


class SignatureCalendarHubTests(TestCase):
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
        self.client = Client()
        self.client.force_login(self.user)

    def _signature_items(self):
        response = self.client.get(reverse("classcalendar:api_events"))
        self.assertEqual(response.status_code, 200)
        return [
            item for item in response.json().get("hub_items") or []
            if item.get("item_kind") == "signature"
        ]

    def test_create_session_shows_signature_hub_item(self):
        session_dt = timezone.localtime(timezone.now() + timedelta(days=2)).replace(minute=0, second=0, microsecond=0)
        response = self.client.post(
            reverse("signatures:create"),
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
        items = self._signature_items()
        item = next(item for item in items if item["id"] == f"signature:{session.uuid}")
        self.assertEqual(item["title"], "서명 연동 테스트")
        self.assertEqual(item["status_label"], "예정")

    def test_edit_and_delete_session_updates_signature_hub_item(self):
        original_dt = timezone.now() + timedelta(days=3)
        session = TrainingSession.objects.create(
            title="초기 연수",
            instructor="강사C",
            datetime=original_dt,
            location="1강의실",
            created_by=self.user,
            is_active=True,
        )

        updated_dt = timezone.localtime(timezone.now() + timedelta(days=5)).replace(minute=30, second=0, microsecond=0)
        edit_response = self.client.post(
            reverse("signatures:edit", kwargs={"uuid": session.uuid}),
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

        edited_item = next(item for item in self._signature_items() if item["id"] == f"signature:{session.uuid}")
        self.assertEqual(edited_item["title"], "수정 연수")

        delete_response = self.client.post(reverse("signatures:delete", kwargs={"uuid": session.uuid}))
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(any(item["id"] == f"signature:{session.uuid}" for item in self._signature_items()))

    def test_create_session_hides_hub_item_when_signature_integration_disabled(self):
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
        self.assertFalse(any(item["id"] == f"signature:{session.uuid}" for item in self._signature_items()))
