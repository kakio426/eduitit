from django.test import TestCase
from django.urls import reverse


class ReflexGameViewTests(TestCase):
    def test_main_page_renders(self):
        response = self.client.get(reverse("reflex_game:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "탭 순발력 챌린지")
        self.assertContains(response, "신호 전에 누르면 반칙")
        self.assertContains(response, "전체화면")

    def test_student_games_mode_sets_hide_navbar_context(self):
        session = self.client.session
        session["dutyticker_student_games_mode"] = {"issuer_id": 1}
        session.save()

        response = self.client.get(reverse("reflex_game:main"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["hide_navbar"])

