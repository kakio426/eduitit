from django.test import TestCase
from django.urls import reverse


class PortfolioPublicViewTests(TestCase):
    def test_portfolio_list_is_public(self):
        response = self.client.get(reverse("portfolio:list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portfolio/portfolio_list.html")

    def test_portfolio_inquiry_is_public(self):
        response = self.client.get(reverse("portfolio:inquiry"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portfolio/inquiry_form.html")

    def test_invalid_inquiry_keeps_input_and_inline_error(self):
        response = self.client.post(
            reverse("portfolio:inquiry"),
            {
                "name": "김교사",
                "organization": "테스트초",
                "email": "not-an-email",
                "phone": "010",
                "topic": "",
                "message": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portfolio/inquiry_form.html")
        self.assertContains(response, "문의 실패")
        self.assertContains(response, "김교사")
        self.assertContains(response, "테스트초")

    def test_inquiry_submit_uses_inline_progress_state(self):
        response = self.client.get(reverse("portfolio:inquiry"))

        self.assertContains(response, "data-portfolio-inquiry-form")
        self.assertContains(response, "data-portfolio-inquiry-submit")
        self.assertContains(response, "전송 중")
