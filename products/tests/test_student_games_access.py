import time
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.core import signing
from django.test import TestCase
from django.urls import reverse

from core.models import SiteConfig, UserProfile
from products import views as product_views


class StudentGamesAccessTests(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.user = User.objects.create_user(
            username="teacher1",
            password="pass1234",
            email="teacher1@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        if not profile.nickname or profile.nickname.startswith("user"):
            profile.nickname = "담임"
            profile.save(update_fields=["nickname"])

        site_config = SiteConfig.load()
        site_config.banner_active = True
        site_config.banner_text = "테스트 배너"
        site_config.save(update_fields=["banner_active", "banner_text"])

    def _issue_token(self):
        payload = {
            "v": 1,
            "issued_at": int(time.time()),
            "issuer_id": self.user.id,
        }
        return signing.dumps(payload, salt=product_views.STUDENT_GAMES_TOKEN_SALT, compress=True)

    def test_dutyticker_view_includes_student_game_qr_for_authenticated_teacher(self):
        self.client.login(username="teacher1", password="pass1234")
        response = self.client.get(reverse("dutyticker"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("student_games_launch_url", response.context)
        self.assertIn("student_games_qr_data_url", response.context)
        self.assertTrue(response.context["student_games_qr_data_url"].startswith("data:image/png;base64,"))

    def test_student_games_launch_enables_session_mode(self):
        token = self._issue_token()
        launch_url = f"{reverse('dt_student_games_launch')}?{urlencode({'token': token})}"

        response = self.client.get(launch_url)
        self.assertRedirects(response, reverse("dt_student_games_portal"))

        session = self.client.session
        self.assertIn(product_views.STUDENT_GAMES_SESSION_KEY, session)

    def test_student_games_launch_rejects_invalid_token(self):
        launch_url = f"{reverse('dt_student_games_launch')}?token=invalid-token"
        response = self.client.get(launch_url)
        self.assertEqual(response.status_code, 403)

    def test_student_mode_blocks_home_and_redirects_to_portal(self):
        session = self.client.session
        session[product_views.STUDENT_GAMES_SESSION_KEY] = {"issuer_id": self.user.id}
        session.save()

        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("dt_student_games_portal"))

    def test_student_mode_allows_game_routes(self):
        session = self.client.session
        session[product_views.STUDENT_GAMES_SESSION_KEY] = {"issuer_id": self.user.id}
        session.save()

        response = self.client.get(reverse("chess:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["hide_navbar"])

    def test_game_page_shows_banner_when_not_in_student_mode(self):
        response = self.client.get(reverse("chess:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="globalBanner"', html=False)

    def test_student_mode_hides_global_banner_on_game_page(self):
        session = self.client.session
        session[product_views.STUDENT_GAMES_SESSION_KEY] = {"issuer_id": self.user.id}
        session.save()

        response = self.client.get(reverse("chess:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="globalBanner"', html=False)
