from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarEvent
from core.models import UserProfile


User = get_user_model()
NOTICE_TITLE = "[안내] 자동 정리 정책 안내"


class RetentionNoticeRemovalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="calendar_notice_user",
            password="pw12345",
            email="calendar_notice_user@example.com",
        )
        self.client = Client()
        self.client.force_login(self.user)
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "알림교사"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])

    def test_legacy_main_does_not_seed_notice_event(self):
        response = self.client.get(reverse("classcalendar:legacy_main"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, f"{reverse('home')}#home-calendar")
        self.assertNotContains(response, NOTICE_TITLE)
        self.assertNotContains(response, "retentionNoticeVisible")
        self.assertFalse(CalendarEvent.objects.filter(author=self.user, title=NOTICE_TITLE).exists())

    def test_manual_notice_titled_event_is_not_duplicated(self):
        CalendarEvent.objects.create(
            author=self.user,
            title=NOTICE_TITLE,
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(minutes=20),
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            source=CalendarEvent.SOURCE_LOCAL,
            is_locked=False,
        )

        self.client.get(reverse("classcalendar:legacy_main"), follow=True)
        self.assertEqual(CalendarEvent.objects.filter(author=self.user, title=NOTICE_TITLE).count(), 1)
