from __future__ import annotations

from dataclasses import dataclass

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from insights.models import Insight
from products.models import Product
from schoolprograms.models import ProgramListing, ProviderProfile

from .discovery_policy import has_public_search_canonical_route, is_sensitive_discovery_target
from .product_visibility import filter_discoverable_products


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
            key="core:about",
            location=reverse("about"),
            changefreq="monthly",
            priority=0.7,
        ),
        PublicSitemapEntry(
            key="products:list",
            location=reverse("product_list"),
            changefreq="weekly",
            priority=0.9,
        ),
        PublicSitemapEntry(
            key="portfolio:list",
            location=reverse("portfolio:list"),
            changefreq="monthly",
            priority=0.7,
        ),
        PublicSitemapEntry(
            key="tools:prompt_lab",
            location=reverse("prompt_lab"),
            changefreq="weekly",
            priority=0.8,
        ),
        PublicSitemapEntry(
            key="insights:list",
            location=reverse("insights:list"),
            changefreq="daily",
            priority=0.9,
        ),
        PublicSitemapEntry(
            key="tools:noticegen",
            location=reverse("noticegen:main"),
            changefreq="weekly",
            priority=0.8,
        ),
        PublicSitemapEntry(
            key="tools:qrgen",
            location=reverse("qrgen:landing"),
            changefreq="weekly",
            priority=0.8,
        ),
        PublicSitemapEntry(
            key="services:collect",
            location=reverse("collect:landing"),
            changefreq="weekly",
            priority=0.8,
        ),
        PublicSitemapEntry(
            key="services:handoff",
            location=reverse("handoff:landing"),
            changefreq="weekly",
            priority=0.8,
        ),
        PublicSitemapEntry(
            key="services:schoolprograms",
            location=reverse("schoolprograms:landing"),
            changefreq="weekly",
            priority=0.8,
        ),
        PublicSitemapEntry(
            key="tools:tts_announce",
            location=reverse("tts_announce"),
            changefreq="weekly",
            priority=0.7,
        ),
    ]

    discoverable_products = filter_discoverable_products(
        Product.objects.filter(is_active=True).order_by("display_order", "-created_at")
    )
    for product in discoverable_products:
        if is_sensitive_discovery_target(product):
            continue
        if has_public_search_canonical_route(product):
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

    approved_listings = ProgramListing.objects.filter(
        approval_status=ProgramListing.ApprovalStatus.APPROVED
    ).select_related("provider")
    for listing in approved_listings.order_by("-published_at", "-id"):
        entries.append(
            PublicSitemapEntry(
                key=f"schoolprograms:listing:{listing.pk}",
                location=reverse("schoolprograms:listing_detail", args=[listing.slug]),
                changefreq="weekly",
                priority=0.7,
                lastmod_source=listing.updated_at,
            )
        )

    approved_provider_ids = approved_listings.values_list("provider_id", flat=True).distinct()
    for provider in ProviderProfile.objects.filter(pk__in=approved_provider_ids).order_by("provider_name", "id"):
        entries.append(
            PublicSitemapEntry(
                key=f"schoolprograms:provider:{provider.pk}",
                location=reverse("schoolprograms:provider_detail", args=[provider.slug]),
                changefreq="monthly",
                priority=0.6,
                lastmod_source=provider.updated_at,
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
