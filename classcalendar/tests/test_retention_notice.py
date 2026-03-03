from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from classcalendar.models import CalendarEvent, CalendarIntegrationSetting, EventPageBlock
from core.models import UserProfile


User = get_user_model()
NOTICE_TITLE = "[안내] 자동 정리 정책 안내"


class RetentionNoticeTests(TestCase):
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

    def test_legacy_main_seeds_notice_event_without_banner(self):
        response = self.client.get(reverse("classcalendar:legacy_main"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "고용량 파일은 90일, 일반 데이터는 1년 기준으로 자동 정리됩니다.")
        self.assertNotContains(response, "캘린더에 같은 안내 일정이 1회 등록되며")

        notice_event = CalendarEvent.objects.filter(author=self.user, title=NOTICE_TITLE).first()
        self.assertIsNotNone(notice_event)
        self.assertFalse(notice_event.is_locked)

        note_block = EventPageBlock.objects.filter(event=notice_event, block_type="text").first()
        self.assertIsNotNone(note_block)
        self.assertIn("90일", str(note_block.content))

        setting = CalendarIntegrationSetting.objects.get(user=self.user)
        self.assertIsNotNone(setting.retention_notice_event_seeded_at)

    def test_dismiss_notice_hides_banner(self):
        self.client.get(reverse("classcalendar:legacy_main"))

        dismiss_response = self.client.post(reverse("classcalendar:api_dismiss_retention_notice"))
        self.assertEqual(dismiss_response.status_code, 200)
        self.assertEqual(dismiss_response.json().get("status"), "success")

        response = self.client.get(reverse("classcalendar:legacy_main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "retentionNoticeVisible: false")
        self.assertFalse(response.context["show_retention_notice_banner"])

        setting = CalendarIntegrationSetting.objects.get(user=self.user)
        self.assertIsNotNone(setting.retention_notice_banner_dismissed_at)

    def test_deleted_notice_event_is_not_recreated(self):
        self.client.get(reverse("classcalendar:legacy_main"))
        notice_event = CalendarEvent.objects.get(author=self.user, title=NOTICE_TITLE)
        notice_event.delete()

        self.client.get(reverse("classcalendar:legacy_main"))
        self.assertFalse(CalendarEvent.objects.filter(author=self.user, title=NOTICE_TITLE).exists())
