from django.contrib.auth.models import User
from django.test import Client
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import SiteConfig, UserProfile
from products import views as product_views
from products.models import DTStudentGamesLaunchTicket


class StudentGamesAccessTests(TestCase):
    def setUp(self):
        self.client = self.client_class()
        self.teacher_client = Client()
        self.student_client = Client()
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

        self.teacher_client.login(username="teacher1", password="pass1234")

    def _issue_ticket_payload(self):
        response = self.teacher_client.post(reverse("dt_student_games_issue"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        return payload

    def test_dutyticker_view_exposes_issue_endpoint_without_token_in_html(self):
        self.client.login(username="teacher1", password="pass1234")
        response = self.client.get(reverse("dutyticker"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["student_games_issue_url"], reverse("dt_student_games_issue"))
        self.assertEqual(response.context["student_games_launch_ttl_minutes"], 15)
        self.assertNotContains(response, "launch/?token=", html=False)
        self.assertContains(response, 'data-student-games-issue-url="/products/dutyticker/student-games/issue/"', html=False)

    def test_student_games_issue_requires_login(self):
        response = self.client.post(reverse("dt_student_games_issue"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "로그인이 필요합니다.")

    def test_student_games_issue_returns_launch_url_and_qr_payload(self):
        payload = self._issue_ticket_payload()
        self.assertIn("/products/dutyticker/student-games/launch/?token=", payload["launch_url"])
        self.assertTrue(payload["qr_data_url"].startswith("data:image/png;base64,"))
        self.assertEqual(payload["expires_in_minutes"], 15)

    def test_student_games_launch_enables_session_mode(self):
        payload = self._issue_ticket_payload()
        response = self.student_client.get(payload["launch_url"])
        self.assertRedirects(response, reverse("dt_student_games_portal"))

        session = self.student_client.session
        self.assertIn(product_views.STUDENT_GAMES_SESSION_KEY, session)
        self.assertEqual(session[product_views.STUDENT_GAMES_SESSION_KEY]["issuer_id"], self.user.id)

    def test_student_games_launch_rejects_invalid_token(self):
        launch_url = f"{reverse('dt_student_games_launch')}?token=invalid-token"
        response = self.student_client.get(launch_url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "선생님께 새 QR을 요청하세요.", status_code=403)

    def test_student_games_reissue_invalidates_previous_ticket(self):
        first_payload = self._issue_ticket_payload()
        second_payload = self._issue_ticket_payload()

        first_response = self.student_client.get(first_payload["launch_url"])
        self.assertEqual(first_response.status_code, 403)

        second_response = self.student_client.get(second_payload["launch_url"])
        self.assertRedirects(second_response, reverse("dt_student_games_portal"))

    def test_student_games_expired_ticket_is_rejected(self):
        payload = self._issue_ticket_payload()
        ticket = DTStudentGamesLaunchTicket.objects.get()
        ticket.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        ticket.save(update_fields=["expires_at"])

        response = self.student_client.get(payload["launch_url"])
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "선생님께 새 QR을 요청하세요.", status_code=403)

    def test_existing_student_session_survives_teacher_reissue(self):
        first_payload = self._issue_ticket_payload()
        launch_response = self.student_client.get(first_payload["launch_url"])
        self.assertRedirects(launch_response, reverse("dt_student_games_portal"))

        second_payload = self._issue_ticket_payload()
        self.assertIn("/products/dutyticker/student-games/launch/?token=", second_payload["launch_url"])

        portal_response = self.student_client.get(reverse("dt_student_games_portal"))
        self.assertEqual(portal_response.status_code, 200)

    def test_student_games_portal_lists_supported_games_and_links_open(self):
        session = self.student_client.session
        session[product_views.STUDENT_GAMES_SESSION_KEY] = {"issuer_id": self.user.id}
        session.save()

        response = self.student_client.get(reverse("dt_student_games_portal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "지금 바로 되는 게임만 모았습니다.")
        self.assertContains(response, "리버시")
        self.assertContains(response, "교실 윷놀이")

        games = response.context["games"]
        titles = {game["title"] for game in games}
        self.assertIn("체스", titles)
        self.assertIn("장기", titles)
        self.assertIn("리버시", titles)
        self.assertIn("탭 순발력 챌린지", titles)
        self.assertIn("교실 윷놀이", titles)
        href_map = {game["title"]: game["href"] for game in games}
        self.assertEqual(href_map["리버시"], reverse("fairy_games:play_reversi"))
        self.assertEqual(href_map["동물 장기"], reverse("fairy_games:play_dobutsu"))

        for game in games:
            route_response = self.student_client.get(game["href"])
            self.assertNotEqual(route_response.status_code, 404, msg=f"broken portal link: {game['title']}")

    def test_student_mode_does_not_block_home(self):
        session = self.client.session
        session[product_views.STUDENT_GAMES_SESSION_KEY] = {"issuer_id": self.user.id}
        session.save()

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_student_mode_allows_game_routes(self):
        session = self.client.session
        session[product_views.STUDENT_GAMES_SESSION_KEY] = {"issuer_id": self.user.id}
        session.save()

        response = self.client.get(reverse("chess:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["hide_navbar"])

    def test_game_page_does_not_show_global_banner(self):
        response = self.client.get(reverse("chess:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="globalBanner"', html=False)

    def test_student_mode_hides_global_banner_on_game_page(self):
        session = self.client.session
        session[product_views.STUDENT_GAMES_SESSION_KEY] = {"issuer_id": self.user.id}
        session.save()

        response = self.client.get(reverse("chess:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="globalBanner"', html=False)
