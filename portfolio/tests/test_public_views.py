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
