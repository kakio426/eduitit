from django.test import TestCase
from django.urls import reverse


class QrgenLandingTests(TestCase):
    def test_landing_shows_public_link_guardrail_copy(self):
        response = self.client.get(reverse("qrgen:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "localhost, 사설 IP, 학교 내부망 주소는 QR로 만들 수 없습니다.")
