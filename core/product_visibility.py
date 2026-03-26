from django.conf import settings
from django.db.models import Q


SHEETBOOK_LEGACY_TITLES = {"교무수첩", "학급 기록 보드"}


def is_sheetbook_runtime_available():
    return bool(getattr(settings, "SHEETBOOK_ENABLED", False))


def is_sheetbook_discovery_visible():
    return is_sheetbook_runtime_available() and bool(
        getattr(settings, "SHEETBOOK_DISCOVERY_VISIBLE", False)
    )


def is_sheetbook_product(product):
    route_name = str(getattr(product, "launch_route_name", "") or "").strip().lower()
    title = str(getattr(product, "title", "") or "").strip()
    if route_name.startswith("sheetbook:"):
        return True
    if route_name:
        return False
    return title in SHEETBOOK_LEGACY_TITLES


def is_product_discoverable(product):
    if not bool(getattr(product, "is_active", False)):
        return False
    if is_sheetbook_product(product) and not is_sheetbook_discovery_visible():
        return False
    return True


def filter_discoverable_products(products):
    if hasattr(products, "filter"):
        queryset = products.filter(is_active=True)
        if not is_sheetbook_discovery_visible():
            queryset = queryset.exclude(launch_route_name__istartswith="sheetbook:").exclude(
                Q(title__in=SHEETBOOK_LEGACY_TITLES)
                & (Q(launch_route_name__isnull=True) | Q(launch_route_name__exact=""))
            )
        return queryset
    return [product for product in products if is_product_discoverable(product)]
