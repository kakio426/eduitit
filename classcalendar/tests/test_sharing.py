from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarEvent, CalendarIntegrationSetting
from core.models import UserProfile

User = get_user_model()


class CalendarSharingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="calendar_share_owner",
            password="pw12345",
            email="calendar_share_owner@example.com",
        )
        self.client = Client()
        self.client.force_login(self.user)
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "공유선생님"
        profile.save(update_fields=["nickname"])

    def test_share_enable_sets_enabled_flag(self):
        response = self.client.post(reverse("classcalendar:share_enable"))
        self.assertEqual(response.status_code, 302)

        setting = CalendarIntegrationSetting.objects.get(user=self.user)
        self.assertTrue(setting.share_enabled)
        self.assertIsNotNone(setting.share_uuid)

    def test_share_rotate_regenerates_uuid_and_enables_share(self):
        setting = CalendarIntegrationSetting.objects.create(user=self.user, share_enabled=False)
        old_uuid = setting.share_uuid

        response = self.client.post(reverse("classcalendar:share_rotate"))
        self.assertEqual(response.status_code, 302)

        setting.refresh_from_db()
        self.assertTrue(setting.share_enabled)
        self.assertNotEqual(setting.share_uuid, old_uuid)

    def test_shared_view_returns_404_when_share_disabled(self):
        setting = CalendarIntegrationSetting.objects.create(user=self.user, share_enabled=False)
        response = Client().get(reverse("classcalendar:shared", kwargs={"share_uuid": setting.share_uuid}))
        self.assertEqual(response.status_code, 404)

    def test_shared_view_shows_events_when_enabled(self):
        setting = CalendarIntegrationSetting.objects.create(user=self.user, share_enabled=True)
        now = timezone.now()
        CalendarEvent.objects.create(
            title="공유 테스트 일정",
            author=self.user,
            start_time=now,
            end_time=now + timedelta(hours=1),
            color="indigo",
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            source=CalendarEvent.SOURCE_LOCAL,
        )

        response = Client().get(reverse("classcalendar:shared", kwargs={"share_uuid": setting.share_uuid}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "공유 테스트 일정")
        self.assertContains(response, "읽기 전용")
