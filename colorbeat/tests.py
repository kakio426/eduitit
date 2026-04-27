from django.test import TestCase
from django.urls import reverse


class ColorbeatViewTest(TestCase):
    def test_main_view_renders_grid_shell(self):
        response = self.client.get(reverse("colorbeat:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "알록달록 비트메이커")
        self.assertContains(response, "colorbeat_pattern_v1")
        self.assertContains(response, "colorbeat_cards_v1")
        self.assertContains(response, "cb-grid")
        self.assertContains(response, "마법")
        self.assertContains(response, "살짝")
        self.assertContains(response, "무대")
        self.assertContains(response, "저장")
