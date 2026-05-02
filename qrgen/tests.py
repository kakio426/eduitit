from django.test import TestCase
from django.urls import reverse


class QrgenLandingTests(TestCase):
    def test_landing_shows_public_link_guardrail_copy(self):
        response = self.client.get(reverse("qrgen:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "링크 확인")

    def test_landing_keeps_cycle_overlay_below_topbar(self):
        response = self.client.get(reverse("qrgen:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "top-[var(--main-nav-height,88px)]")
        self.assertContains(response, "QR 준비 실패")
