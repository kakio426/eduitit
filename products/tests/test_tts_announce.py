from datetime import time

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from happy_seed.models import HSClassroom
from products.models import DTSchedule
from products.tts_announcement import build_demo_tts_rows, build_tts_announcement_text

User = get_user_model()


class TTSAnnouncementHelperTests(TestCase):
    def test_build_tts_announcement_text_uses_period_and_subject(self):
        self.assertEqual(
            build_tts_announcement_text(1, "과학"),
            "1교시 5분 전입니다. 1교시는 과학입니다!",
        )

    def test_demo_rows_provide_immediate_preview(self):
        rows = build_demo_tts_rows()
        self.assertGreaterEqual(len(rows), 4)
        self.assertTrue(rows[0]["announcement_text"].startswith("1교시"))
        self.assertTrue(rows[0]["is_demo"])


class TTSAnnouncementViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tts_teacher",
            password="pw12345",
            email="tts_teacher@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "담임교사"
        profile.save(update_fields=["nickname"])
        self.client = Client()
        self.client.force_login(self.user)

        self.classroom = HSClassroom.objects.create(
            teacher=self.user,
            name="4학년 1반",
            slug="tts-4-1",
        )
        session = self.client.session
        session["active_classroom_source"] = "hs"
        session["active_classroom_id"] = str(self.classroom.id)
        session.save()

    def test_view_uses_saved_schedule_when_available(self):
        today_js_day = (timezone.localdate().weekday() + 1) % 7
        DTSchedule.objects.create(
            user=self.user,
            classroom=self.classroom,
            day=today_js_day,
            period=1,
            subject="과학",
            start_time=time(hour=9, minute=0),
            end_time=time(hour=9, minute=40),
        )

        response = self.client.get(reverse("tts_announce"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["schedule_source_label"], "저장된 시간표")
        self.assertContains(response, "교시 안내 TTS")
        self.assertContains(response, "과학")
        self.assertEqual(response.context["schedule_rows"][0]["subject"], "과학")
        self.assertIn("과학", response.context["next_announcement_text"])

    def test_view_falls_back_to_demo_rows_for_anonymous_visitors(self):
        anonymous_client = Client()

        response = anonymous_client.get(reverse("tts_announce"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["schedule_source_label"], "샘플 시간표")
        self.assertContains(response, "샘플")
        self.assertGreaterEqual(len(response.context["schedule_rows"]), 4)
