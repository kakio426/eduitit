from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import UserProfile

User = get_user_model()


class CalendarEntryRouteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="calendar_entry_user",
            password="pw12345",
            email="calendar_entry_user@example.com",
        )
        self.client = Client()
        self.client.force_login(self.user)
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "entry_user", "role": "school"},
        )

    def test_main_route_renders_independent_calendar_center(self):
        response = self.client.get(reverse("classcalendar:main"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-classcalendar-center="true"', content)
        self.assertIn('data-classcalendar-embed-mode="page"', content)

    def test_entry_route_redirects_to_home_calendar(self):
        response = self.client.get(reverse("classcalendar:entry"))
        self.assertRedirects(response, f"{reverse('home')}#home-calendar", fetch_redirect_response=False)

    def test_entry_route_with_legacy_query_redirects_to_home_calendar(self):
        response = self.client.get(f"{reverse('classcalendar:entry')}?legacy=1")
        self.assertRedirects(response, f"{reverse('home')}#home-calendar", fetch_redirect_response=False)
