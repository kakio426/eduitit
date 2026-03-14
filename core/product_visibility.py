from django.conf import settings


def is_sheetbook_discovery_visible():
    return bool(getattr(settings, "SHEETBOOK_DISCOVERY_VISIBLE", False))


def is_product_discoverable(product):
    return bool(getattr(product, "is_active", False))


def filter_discoverable_products(products):
    if hasattr(products, "filter"):
        return products.filter(is_active=True)
    return [product for product in products if is_product_discoverable(product)]
