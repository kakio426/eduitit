from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.admin_navigation import build_admin_navigation


class BuildAdminNavigationTests(SimpleTestCase):
    def test_known_apps_are_grouped_and_leftovers_fall_back_to_legacy(self):
        app_list = [
            {
                "app_label": "auth",
                "name": "Authentication and Authorization",
                "app_url": "/secret-admin-kakio/auth/",
                "models": [
                    {
                        "name": "Users",
                        "object_name": "User",
                        "admin_url": "/secret-admin-kakio/auth/user/",
                        "add_url": "/secret-admin-kakio/auth/user/add/",
                    }
                ],
            },
            {
                "app_label": "core",
                "name": "Core",
                "app_url": "/secret-admin-kakio/core/",
                "models": [
                    {
                        "name": "Site configs",
                        "object_name": "SiteConfig",
                        "admin_url": "/secret-admin-kakio/core/siteconfig/",
                        "add_url": "/secret-admin-kakio/core/siteconfig/add/",
                    }
                ],
            },
            {
                "app_label": "artclass",
                "name": "미술 수업",
                "app_url": "/secret-admin-kakio/artclass/",
                "models": [
                    {
                        "name": "미술 수업",
                        "object_name": "ArtClass",
                        "admin_url": "/secret-admin-kakio/artclass/artclass/",
                        "add_url": "/secret-admin-kakio/artclass/artclass/add/",
                    }
                ],
            },
        ]

        groups = build_admin_navigation(
            app_list,
            current_path="/secret-admin-kakio/artclass/artclass/",
        )

        self.assertEqual([group["key"] for group in groups], ["operations", "legacy"])
        self.assertEqual(
            [app["app_label"] for app in groups[0]["apps"]],
            ["core", "auth"],
        )
        self.assertFalse(groups[0]["has_current"])
        self.assertTrue(groups[1]["has_current"])
        self.assertEqual(groups[1]["apps"][0]["app_label"], "artclass")
        self.assertTrue(groups[1]["apps"][0]["models"][0]["is_current"])


class AdminNavigationTemplateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password123",
        )
        self.client.force_login(self.user)

    def test_admin_index_uses_grouped_navigation_copy(self):
        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "운영 · 계정")
        self.assertContains(response, "기존 · 보관 서비스")
        self.assertContains(response, "서비스와 DB 메뉴를 빠르게 찾기")

    def test_admin_change_list_loads_enhanced_sidebar_assets(self):
        response = self.client.get(reverse("admin:auth_user_changelist"))

        self.assertContains(response, "core/js/admin_navigation.js")
        self.assertContains(response, 'data-admin-group="operations"', html=False)
