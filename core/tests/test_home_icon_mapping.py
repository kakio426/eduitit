from pathlib import Path

from django.test import SimpleTestCase

from core.service_launcher import resolve_home_icon_class


REPO_ROOT = Path(__file__).resolve().parents[2]


class HomeIconMappingTests(SimpleTestCase):
    def test_home_templates_do_not_keep_legacy_sparkles_fallbacks(self):
        template_paths = [
            "core/templates/core/home_authenticated_v6_canonical.html",
            "core/templates/core/home_public_v6_canonical.html",
            "core/templates/core/partials/home_public_v6_desktop.html",
            "core/templates/core/home_public_v5.html",
            "core/templates/core/partials/home_public_v5_desktop.html",
            "core/templates/core/home_authenticated_v5.html",
            "core/templates/core/home_authenticated_v4.html",
            "core/templates/core/home_authenticated_v2.html",
            "core/templates/core/home_v2.html",
            "core/templates/core/home_public_v4.html",
            "core/templates/core/includes/guest_access_highlight_card.html",
            "core/templates/core/partials/home_v4_mobile_quick_tools.html",
            "core/templates/core/partials/home_v4_nav_sections.html",
            "core/templates/core/includes/mini_card.html",
            "core/templates/core/partials/home_v6_nav_sections.html",
        ]

        for relative_path in template_paths:
            with self.subTest(path=relative_path):
                template = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("fa-solid fa-sparkles", template)

    def test_fortune_routes_use_supported_star_icon(self):
        self.assertEqual(resolve_home_icon_class(route_name="fortune:saju"), "fa-solid fa-star")
        self.assertEqual(resolve_home_icon_class(route_name="saju:landing"), "fa-solid fa-star")

    def test_legacy_home_icon_aliases_are_normalized_for_home_surfaces(self):
        self.assertEqual(
            resolve_home_icon_class(icon="fa-solid fa-sparkles"),
            "fa-solid fa-star",
        )
        self.assertEqual(
            resolve_home_icon_class(icon="fa-solid fa-up-right-from-square"),
            "fa-solid fa-arrow-up-right-from-square",
        )

    def test_title_keyword_fallbacks_keep_refresh_icons_deterministic(self):
        self.assertEqual(
            resolve_home_icon_class(title="선생님 사주"),
            "fa-solid fa-star",
        )
        self.assertEqual(
            resolve_home_icon_class(title="쌤BTI"),
            "fa-solid fa-id-badge",
        )
