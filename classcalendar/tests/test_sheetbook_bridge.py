from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile
from sheetbook.models import SheetTab, Sheetbook

User = get_user_model()


class CalendarSheetbookBridgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="calendar_bridge_user",
            password="pw12345",
            email="calendar_bridge_user@example.com",
        )
        self.client = Client()
        self.client.force_login(self.user)
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "bridge_user", "role": "school"},
        )

    @override_settings(SHEETBOOK_ENABLED=False)
    def test_main_route_renders_legacy_calendar_when_sheetbook_disabled(self):
        response = self.client.get(reverse("classcalendar:main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "캘린더에서 일정을 바로 확인하고 관리하세요.")

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_main_route_renders_bridge_when_sheetbook_enabled(self):
        response = self.client.get(reverse("classcalendar:main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교무수첩 만들기")
        self.assertContains(response, reverse("classcalendar:legacy_main"))

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_bridge_shows_sheetbook_calendar_entry_when_sheetbook_exists(self):
        sheetbook = Sheetbook.objects.create(owner=self.user, title="2026 3-1 교무수첩")
        calendar_tab = SheetTab.objects.create(
            sheetbook=sheetbook,
            name="달력",
            tab_type=SheetTab.TYPE_CALENDAR,
            sort_order=1,
        )

        response = self.client.get(reverse("classcalendar:main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교무수첩 달력 탭으로 이동")
        self.assertContains(response, "2026 3-1 교무수첩")
        self.assertContains(response, f"{reverse('sheetbook:detail', kwargs={'pk': sheetbook.pk})}?tab={calendar_tab.pk}")

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_main_route_with_legacy_query_renders_existing_calendar(self):
        response = self.client.get(f"{reverse('classcalendar:main')}?legacy=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "캘린더에서 일정을 바로 확인하고 관리하세요.")
