from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.urls import reverse


REPO_ROOT = Path(__file__).resolve().parents[2]


class GlobalShellPaletteTests(SimpleTestCase):
    def test_base_shell_css_keeps_current_purple_brand_tokens(self):
        css = (REPO_ROOT / "core/static/core/css/base.css").read_text(encoding="utf-8")

        self.assertIn("--color-brand-700: #6844c6;", css)
        self.assertIn("--color-brand-900: #1f1538;", css)
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
        self.assertContains(response, "auth-shell-brand-icon")
        self.assertContains(response, "images/eduitit_logo_mark.png")
        self.assertContains(response, "auth-login-panel")
        self.assertContains(response, "선생님의 하루를")
        self.assertContains(response, "교육에만")
        self.assertContains(response, "소셜 계정으로 로그인")
        self.assertNotContains(response, "M14 13L11 16")
        self.assertNotContains(response, "내 교실 열기")
        self.assertNotContains(response, "로그인하고 교실 업무 이어서")
        self.assertNotContains(response, "bot_login_input")

    def test_signup_page_uses_same_brand_icon_as_login(self):
        response = self.client.get(reverse("account_signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "core/css/auth_chrome.css")
        self.assertContains(response, "auth-shell-brand")
        self.assertContains(response, "images/eduitit_logo_mark.png")
        self.assertNotContains(response, "fa-solid fa-user-plus")
        self.assertContains(response, "이메일과 닉네임만 확인하면 시작합니다.")
