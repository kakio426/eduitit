from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from classcalendar.models import CalendarEvent
from core.views import _build_today_context

User = get_user_model()


class TodayWidgetTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="teacher", password="pw")

    def _build_request(self):
        request = self.factory.get("/")
        request.user = self.user
        return request

    def test_today_context_includes_classcalendar_item_when_today_event_exists(self):
        now = timezone.localtime()
        CalendarEvent.objects.create(
            title="오늘 수업",
            start_time=now,
            end_time=now + timezone.timedelta(hours=1),
            author=self.user,
        )

        context = _build_today_context(self._build_request())
        item = next((x for x in context["today_items"] if x["href"] == reverse("classcalendar:main")), None)

        self.assertIsNotNone(item)
        self.assertEqual(item["count_text"], "1건")
