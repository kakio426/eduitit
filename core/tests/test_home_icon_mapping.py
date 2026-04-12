from django.test import SimpleTestCase

from core.service_launcher import resolve_home_icon_class


class HomeIconMappingTests(SimpleTestCase):
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
