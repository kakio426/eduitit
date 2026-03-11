from django.test import TestCase
from django.urls import reverse

from core.service_launcher import build_service_launcher_items
from core.views import _resolve_product_launch_url
from products.models import Product


class ProductLaunchRouteTests(TestCase):
    def test_launch_route_name_defaults_to_blank(self):
        product = Product.objects.create(
            title="Route Field Default",
            description="desc",
            price=0,
            is_active=True,
        )
        self.assertEqual(product.launch_route_name, "")

    def test_resolver_uses_launch_route_name(self):
        product = Product.objects.create(
            title="Route Field Preferred",
            description="desc",
            price=0,
            is_active=True,
            launch_route_name="collect:landing",
        )

        href, is_external = _resolve_product_launch_url(product)
        self.assertEqual(href, reverse("collect:landing"))
        self.assertFalse(is_external)

    def test_resolver_falls_back_to_product_detail_when_no_target(self):
        product = Product.objects.create(
            title="No Route Product",
            description="desc",
            price=0,
            is_active=True,
        )

        href, is_external = _resolve_product_launch_url(product)
        self.assertEqual(href, reverse("product_detail", kwargs={"pk": product.pk}))
        self.assertFalse(is_external)

    def test_resolver_no_longer_uses_title_based_fallback(self):
        product = Product.objects.create(
            title="간편 수합",
            description="desc",
            price=0,
            is_active=True,
            launch_route_name="",
            external_url="",
        )

        href, is_external = _resolve_product_launch_url(product)
        self.assertEqual(href, reverse("product_detail", kwargs={"pk": product.pk}))
        self.assertFalse(is_external)

    def test_resolver_prefers_launch_route_over_internal_external_path(self):
        product = Product.objects.create(
            title="Legacy Internal Path Product",
            description="desc",
            price=0,
            is_active=True,
            launch_route_name="collect:landing",
            external_url="/collect/",
        )

        href, is_external = _resolve_product_launch_url(product)
        self.assertEqual(href, reverse("collect:landing"))
        self.assertFalse(is_external)

    def test_service_launcher_uses_same_launch_ssot(self):
        product = Product.objects.create(
            title="Launcher Route Product",
            description="desc",
            solve_text="바로 실행합니다",
            price=0,
            is_active=True,
            launch_route_name="collect:landing",
            service_type="collect_sign",
        )

        href, is_external = _resolve_product_launch_url(product)
        launcher_item = build_service_launcher_items([product])[0]

        self.assertEqual(launcher_item["href"], href)
        self.assertEqual(launcher_item["is_external"], is_external)
