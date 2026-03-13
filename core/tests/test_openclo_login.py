from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.models import SiteConfig, UserProfile
from core.openclo_login import OPENCLO_LOGIN_URL


def _create_ready_user():
    user = User.objects.create_user(
        username="openclo_teacher",
        email="openclo_teacher@example.com",
        password="password123",
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = "openclo-teacher"
    profile.role = "school"
    profile.save()
    return user


class OpenCloHiddenLoginViewTests(TestCase):
    def setUp(self):
        self.user = _create_ready_user()

    def test_hidden_login_page_renders_manual_credentials_form(self):
        response = self.client.get(OPENCLO_LOGIN_URL)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-openclo-form="login"')
        self.assertContains(response, 'data-openclo-field="username"')
        self.assertContains(response, 'data-openclo-field="password"')
        self.assertContains(response, 'data-openclo-action="submit-login"')
        self.assertEqual(
            response.headers.get("X-Robots-Tag"),
            "noindex, nofollow, noarchive, nosnippet",
        )
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        self.assertEqual(response.headers.get("Referrer-Policy"), "same-origin")
        self.assertContains(response, 'content="same-origin"')
        self.assertNotContains(response, 'content="no-referrer"')

    def test_hidden_login_page_authenticates_username_password(self):
        response = self.client.post(
            OPENCLO_LOGIN_URL,
            {
                "username": "openclo_teacher",
                "password": "password123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue("_auth_user_id" in self.client.session)

    def test_hidden_login_page_authenticates_email_password(self):
        response = self.client.post(
            OPENCLO_LOGIN_URL,
            {
                "username": "openclo_teacher@example.com",
                "password": "password123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue("_auth_user_id" in self.client.session)


@override_settings(MAINTENANCE_MODE=False)
class OpenCloHiddenLoginMaintenanceAccessTests(TestCase):
    def test_hidden_login_page_stays_available_during_site_config_maintenance(self):
        config = SiteConfig.load()
        config.maintenance_mode = True
        config.save()

        response = self.client.get(OPENCLO_LOGIN_URL)

        self.assertNotEqual(response.status_code, 503)


@override_settings(MAINTENANCE_MODE=True)
class OpenCloHiddenLoginEnvMaintenanceAccessTests(TestCase):
    def test_hidden_login_page_stays_available_during_env_maintenance(self):
        response = self.client.get(OPENCLO_LOGIN_URL)

        self.assertNotEqual(response.status_code, 503)
