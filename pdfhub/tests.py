import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class PdfhubViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pdfhub-user",
            email="pdfhub-user@example.com",
            password="pass1234",
        )
        profile = self.user.userprofile
        profile.nickname = "PDF선생"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("pdfhub:main"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login", response["Location"])
        self.assertIn("/pdf/", response["Location"])

    def test_authenticated_user_can_open_hub(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("pdfhub:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PDF 작업실")

    def test_existing_service_links_are_rendered(self):
        self.client.force_login(self.user)
        routes = (
            "docviewer:main",
            "docsign:list",
            "consent:dashboard",
            "textbooks:main",
            "textbook_ai:main",
            "signatures:list",
            "version_manager:document_list",
        )

        response = self.client.get(reverse("pdfhub:main"))

        for route in routes:
            self.assertContains(response, f'href="{reverse(route)}"')

    def test_stirling_candidates_are_disabled_without_href(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("pdfhub:main"))
        html = response.content.decode()

        for key in ("merge", "split", "compress"):
            self.assertRegex(
                html,
                rf'<div[^>]+data-pdfhub-next="{key}"[^>]+aria-disabled="true"',
            )
            self.assertIsNone(re.search(rf'<a[^>]+data-pdfhub-next="{key}"', html))

    def test_sheetbook_is_not_rendered(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("pdfhub:main"))

        self.assertNotContains(response, "sheetbook")
        self.assertNotContains(response, "Sheetbook")
