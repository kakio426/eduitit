from django.conf import settings


CALENDAR_DISCOVERY_ROUTE_NAME = "classcalendar:main"
SHEETBOOK_DISCOVERY_ROUTE_NAME = "sheetbook:index"


def is_sheetbook_discovery_visible():
    return bool(getattr(settings, "SHEETBOOK_DISCOVERY_VISIBLE", False))


def is_product_discoverable(product):
    route_name = getattr(product, "launch_route_name", "")
    if route_name == CALENDAR_DISCOVERY_ROUTE_NAME:
        return False
    if is_sheetbook_discovery_visible():
        return True
    return route_name != SHEETBOOK_DISCOVERY_ROUTE_NAME


def filter_discoverable_products(products):
    hidden_routes = {CALENDAR_DISCOVERY_ROUTE_NAME}
    if not is_sheetbook_discovery_visible():
        hidden_routes.add(SHEETBOOK_DISCOVERY_ROUTE_NAME)
    if is_sheetbook_discovery_visible():
        if hasattr(products, "exclude"):
            return products.exclude(launch_route_name=CALENDAR_DISCOVERY_ROUTE_NAME)
        return [product for product in products if is_product_discoverable(product)]
    if hasattr(products, "exclude"):
        return products.exclude(launch_route_name__in=hidden_routes)
    return [product for product in products if is_product_discoverable(product)]
