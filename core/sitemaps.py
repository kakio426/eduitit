from __future__ import annotations

from dataclasses import dataclass

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from insights.models import Insight
from products.models import Product, ServiceManual

from .discovery_policy import is_sensitive_discovery_target
from .product_visibility import filter_discoverable_manuals, filter_discoverable_products


@dataclass(frozen=True)
class PublicSitemapEntry:
    key: str
    location: str
    changefreq: str
    priority: float
    lastmod_source: object | None = None
    is_indexable: bool = True


def build_public_sitemap_entries() -> tuple[PublicSitemapEntry, ...]:
    entries: list[PublicSitemapEntry] = [
        PublicSitemapEntry(
            key="core:home",
            location=reverse("home"),
            changefreq="daily",
            priority=1.0,
        ),
        PublicSitemapEntry(
            key="tools:tool_guide",
            location=reverse("tool_guide"),
            changefreq="weekly",
            priority=0.8,
        ),
        PublicSitemapEntry(
            key="manuals:list",
            location=reverse("service_guide_list"),
            changefreq="weekly",
            priority=0.8,
        ),
        PublicSitemapEntry(
            key="insights:list",
            location=reverse("insights:list"),
            changefreq="daily",
            priority=0.9,
        ),
    ]

    published_manuals = filter_discoverable_manuals(ServiceManual.objects.filter(
        is_published=True,
        product__is_active=True,
    ).select_related("product"))
    for manual in published_manuals:
        if is_sensitive_discovery_target(manual):
            continue
        entries.append(
            PublicSitemapEntry(
                key=f"manuals:{manual.pk}",
                location=reverse("service_guide_detail", kwargs={"pk": manual.pk}),
                changefreq="weekly",
                priority=0.7,
                lastmod_source=manual.updated_at,
            )
        )

    discoverable_products = filter_discoverable_products(
        Product.objects.filter(is_active=True).order_by("display_order", "-created_at")
    )
    for product in discoverable_products:
        if is_sensitive_discovery_target(product):
            continue
        entries.append(
            PublicSitemapEntry(
                key=f"products:{product.pk}",
                location=reverse("product_detail", kwargs={"pk": product.pk}),
                changefreq="weekly",
                priority=0.6,
                lastmod_source=product.updated_at,
            )
        )

    for insight in Insight.objects.order_by("-updated_at"):
        entries.append(
            PublicSitemapEntry(
                key=f"insights:{insight.pk}",
                location=reverse("insights:detail", kwargs={"pk": insight.pk}),
                changefreq="monthly",
                priority=0.7,
                lastmod_source=insight.updated_at,
            )
        )

    return tuple(entry for entry in entries if entry.is_indexable)


class PublicUrlSitemap(Sitemap):
    protocol = "https"

    def items(self):
        return build_public_sitemap_entries()

    def location(self, item: PublicSitemapEntry):
        return item.location

    def changefreq(self, item: PublicSitemapEntry):
        return item.changefreq

    def priority(self, item: PublicSitemapEntry):
        return item.priority

    def lastmod(self, item: PublicSitemapEntry):
        return item.lastmod_source
