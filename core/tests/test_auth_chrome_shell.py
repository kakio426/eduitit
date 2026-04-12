from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.urls import reverse


REPO_ROOT = Path(__file__).resolve().parents[2]


class GlobalShellPaletteTests(SimpleTestCase):
    def test_base_shell_css_uses_blue_brand_tokens_instead_of_legacy_purple(self):
        css = (REPO_ROOT / "core/static/core/css/base.css").read_text(encoding="utf-8")

        self.assertIn("--color-brand-700: #2457c5;", css)
        self.assertIn("--color-brand-900: #173b67;", css)
        self.assertNotIn("#5b2ccf", css)
        self.assertNotIn("#43206f", css)
        self.assertNotIn("rgba(91, 44, 207", css)

    def test_auth_chrome_css_avoids_legacy_purple_focus_and_surface_values(self):
        css = (REPO_ROOT / "core/static/core/css/auth_chrome.css").read_text(encoding="utf-8")

        self.assertIn("rgba(36, 87, 197, 0.13)", css)
        self.assertIn("background-color: #f4f7fb;", css)
        self.assertNotIn("rgba(91, 44, 207", css)
        self.assertNotIn("rgba(245, 241, 255", css)


class AuthChromeTemplateTests(TestCase):
    def test_login_page_uses_shared_auth_chrome_shell(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "core/css/auth_chrome.css")
        self.assertContains(response, "auth-shell-brand")
        self.assertContains(response, "fa-solid fa-cloud")

    def test_signup_page_uses_same_brand_icon_as_login(self):
        response = self.client.get(reverse("account_signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "core/css/auth_chrome.css")
        self.assertContains(response, "auth-shell-brand")
        self.assertContains(response, "fa-solid fa-cloud")
        self.assertNotContains(response, "fa-solid fa-user-plus")
