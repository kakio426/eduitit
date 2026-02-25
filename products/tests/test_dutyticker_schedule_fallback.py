from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarEvent
from products.models import DTRole, DTSchedule, DTStudent

User = get_user_model()


class DutyTickerScheduleFallbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dutyticker_schedule_user",
            password="pw12345",
            email="dutyticker_schedule_user@example.com",
        )
        self.client = Client()
        self.client.force_login(self.user)

        # Prevent auto mockup seeding path in dt_api_data by ensuring at least one student/role exists.
        DTStudent.objects.create(user=self.user, name="테스트 학생", number=1)
        DTRole.objects.create(user=self.user, name="칠판 지우기", time_slot="쉬는시간")

    def test_api_data_falls_back_to_classcalendar_when_dtschedule_missing(self):
        now = timezone.now()
        CalendarEvent.objects.create(
            title="오늘 공개수업",
            author=self.user,
            start_time=now.replace(hour=9, minute=0, second=0, microsecond=0),
            end_time=now.replace(hour=9, minute=40, second=0, microsecond=0),
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            source=CalendarEvent.SOURCE_LOCAL,
            color="indigo",
        )

        response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        today_js_day = (timezone.localdate().weekday() + 1) % 7
        today_rows = payload["schedule"].get(str(today_js_day), [])
        self.assertTrue(today_rows)
        self.assertEqual(today_rows[0]["name"], "오늘 공개수업")

    def test_api_data_keeps_dtschedule_when_today_schedule_exists(self):
        today_js_day = (timezone.localdate().weekday() + 1) % 7
        DTSchedule.objects.create(
            user=self.user,
            day=today_js_day,
            period=1,
            subject="국어",
            start_time=time(hour=9, minute=0),
            end_time=time(hour=9, minute=40),
        )

        now = timezone.now()
        CalendarEvent.objects.create(
            title="fallback should not override",
            author=self.user,
            start_time=now,
            end_time=now + timedelta(hours=1),
            visibility=CalendarEvent.VISIBILITY_TEACHER,
            source=CalendarEvent.SOURCE_LOCAL,
            color="indigo",
        )

        response = self.client.get(reverse("dt_api_data"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        today_rows = payload["schedule"].get(str(today_js_day), [])
        self.assertTrue(today_rows)
        self.assertEqual(today_rows[0]["name"], "국어")
