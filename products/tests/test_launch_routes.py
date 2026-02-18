from django.test import TestCase
from django.urls import reverse

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
