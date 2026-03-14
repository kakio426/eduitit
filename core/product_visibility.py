from django.conf import settings


GUEST_PUBLIC_PRODUCT_ROUTE_ORDER = {
    "ssambti:main": 0,
    "tool_guide": 1,
    "insights:list": 2,
    "fortune:saju": 4,
    "yut_game": 5,
    "chess:index": 6,
    "janggi:index": 7,
}
GUEST_PUBLIC_GAME_ROUTE_NAMES = frozenset({"yut_game", "chess:index", "janggi:index"})
GUEST_PUBLIC_EXTERNAL_RANK = 3
GUEST_PUBLIC_EXTERNAL_TITLES = ("유튜브 탈알고리즘",)
GUEST_PUBLIC_EXTERNAL_HOST_HINTS = ("motube-woad.vercel.app",)


def is_sheetbook_discovery_visible():
    return bool(getattr(settings, "SHEETBOOK_DISCOVERY_VISIBLE", False))


def _request_is_authenticated(request):
    user = getattr(request, "user", None)
    return bool(user and getattr(user, "is_authenticated", False))


def _normalize_text(value):
    return " ".join(str(value or "").strip().lower().split())


def _product_route_name(product):
    return _normalize_text(getattr(product, "launch_route_name", ""))


def _product_title_text(product):
    return _normalize_text(getattr(product, "title", ""))


def _product_external_url(product):
    return _normalize_text(getattr(product, "external_url", ""))


def get_guest_public_product_rank(product):
    route_name = _product_route_name(product)
    if route_name in GUEST_PUBLIC_PRODUCT_ROUTE_ORDER:
        return GUEST_PUBLIC_PRODUCT_ROUTE_ORDER[route_name]

    title = _product_title_text(product)
    external_url = _product_external_url(product)
    if any(keyword.lower() in title for keyword in GUEST_PUBLIC_EXTERNAL_TITLES):
        return GUEST_PUBLIC_EXTERNAL_RANK
    if any(host in external_url for host in GUEST_PUBLIC_EXTERNAL_HOST_HINTS):
        return GUEST_PUBLIC_EXTERNAL_RANK
    return None


def is_guest_public_product_candidate(product):
    return get_guest_public_product_rank(product) is not None


def is_guest_public_game_product(product):
    return _product_route_name(product) in GUEST_PUBLIC_GAME_ROUTE_NAMES


def sort_guest_public_products(products):
    indexed_products = list(enumerate(products))
    indexed_products.sort(
        key=lambda item: (
            get_guest_public_product_rank(item[1]),
            item[0],
            getattr(item[1], "display_order", 0) or 0,
            _product_title_text(item[1]),
        )
    )
    return [product for _, product in indexed_products]


def is_product_discoverable(product, request=None):
    if not bool(getattr(product, "is_active", False)):
        return False
    if _request_is_authenticated(request):
        return True
    return is_guest_public_product_candidate(product)


def filter_discoverable_products(products, request=None):
    if _request_is_authenticated(request):
        if hasattr(products, "filter"):
            return products.filter(is_active=True)
        return [product for product in products if bool(getattr(product, "is_active", False))]

    visible_products = [
        product
        for product in products
        if bool(getattr(product, "is_active", False)) and is_guest_public_product_candidate(product)
    ]
    return sort_guest_public_products(visible_products)


def is_manual_discoverable(manual, request=None):
    product = getattr(manual, "product", None)
    return product is not None and is_product_discoverable(product, request=request)


def filter_discoverable_manuals(manuals, request=None):
    if _request_is_authenticated(request):
        return manuals

    visible_manuals = [manual for manual in manuals if is_manual_discoverable(manual, request=request)]
    visible_manuals.sort(
        key=lambda manual: (
            get_guest_public_product_rank(manual.product),
            getattr(manual.product, "display_order", 0) or 0,
            _product_title_text(manual.product),
            _normalize_text(getattr(manual, "title", "")),
        )
    )
    return visible_manuals
