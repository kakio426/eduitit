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
    def test_main_route_renders_calendar_when_sheetbook_disabled(self):
        response = self.client.get(reverse("classcalendar:main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "새 일정")

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_main_route_renders_calendar_when_sheetbook_enabled(self):
        response = self.client.get(reverse("classcalendar:main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "새 일정")
        self.assertNotContains(response, "교무수첩 만들기")

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_sheetbook_entry_route_redirects_to_main_when_no_sheetbook_exists(self):
        response = self.client.get(reverse("classcalendar:sheetbook_entry"))
        self.assertRedirects(response, reverse("classcalendar:main"))

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_sheetbook_entry_shows_sheetbook_calendar_entry_when_sheetbook_exists(self):
        sheetbook = Sheetbook.objects.create(owner=self.user, title="2026 3-1 교무수첩")
        calendar_tab = SheetTab.objects.create(
            sheetbook=sheetbook,
            name="달력",
            tab_type=SheetTab.TYPE_CALENDAR,
            sort_order=1,
        )

        response = self.client.get(reverse("classcalendar:sheetbook_entry"))
        self.assertRedirects(response, f"{reverse('sheetbook:detail', kwargs={'pk': sheetbook.pk})}?tab={calendar_tab.pk}")

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_sheetbook_entry_prefers_recent_sheetbook_from_session(self):
        recent_sheetbook = Sheetbook.objects.create(owner=self.user, title="최근 연 수첩")
        recent_tab = SheetTab.objects.create(
            sheetbook=recent_sheetbook,
            name="달력",
            tab_type=SheetTab.TYPE_CALENDAR,
            sort_order=1,
        )
        newer_sheetbook = Sheetbook.objects.create(owner=self.user, title="최근 수정 수첩")
        SheetTab.objects.create(
            sheetbook=newer_sheetbook,
            name="달력",
            tab_type=SheetTab.TYPE_CALENDAR,
            sort_order=1,
        )

        session = self.client.session
        session["sheetbook_recent_sheetbook_id"] = recent_sheetbook.id
        session.save()

        response = self.client.get(reverse("classcalendar:sheetbook_entry"))
        self.assertRedirects(response, f"{reverse('sheetbook:detail', kwargs={'pk': recent_sheetbook.pk})}?tab={recent_tab.pk}")

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_sheetbook_entry_prefers_explicit_calendar_link_over_recent_sheetbook(self):
        explicit_sheetbook = Sheetbook.objects.create(owner=self.user, title="직접 연결 수첩")
        explicit_tab = SheetTab.objects.create(
            sheetbook=explicit_sheetbook,
            name="달력",
            tab_type=SheetTab.TYPE_CALENDAR,
            sort_order=1,
        )
        explicit_sheetbook.preferred_calendar_tab = explicit_tab
        explicit_sheetbook.save(update_fields=["preferred_calendar_tab", "updated_at"])

        recent_sheetbook = Sheetbook.objects.create(owner=self.user, title="최근 연 수첩")
        recent_tab = SheetTab.objects.create(
            sheetbook=recent_sheetbook,
            name="달력",
            tab_type=SheetTab.TYPE_CALENDAR,
            sort_order=1,
        )

        session = self.client.session
        session["sheetbook_recent_sheetbook_id"] = recent_sheetbook.id
        session.save()

        response = self.client.get(reverse("classcalendar:sheetbook_entry"))
        self.assertRedirects(response, f"{reverse('sheetbook:detail', kwargs={'pk': explicit_sheetbook.pk})}?tab={explicit_tab.pk}")

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_sheetbook_entry_with_legacy_query_redirects_to_main(self):
        response = self.client.get(f"{reverse('classcalendar:sheetbook_entry')}?legacy=1")
        self.assertRedirects(response, reverse("classcalendar:main"))
