from django.conf import settings


SHEETBOOK_DISCOVERY_ROUTE_NAME = "sheetbook:index"


def is_sheetbook_discovery_visible():
    return bool(getattr(settings, "SHEETBOOK_DISCOVERY_VISIBLE", False))


def is_product_discoverable(product):
    if is_sheetbook_discovery_visible():
        return True
    return getattr(product, "launch_route_name", "") != SHEETBOOK_DISCOVERY_ROUTE_NAME


def filter_discoverable_products(products):
    if is_sheetbook_discovery_visible():
        return products
    if hasattr(products, "exclude"):
        return products.exclude(launch_route_name=SHEETBOOK_DISCOVERY_ROUTE_NAME)
    return [product for product in products if is_product_discoverable(product)]
