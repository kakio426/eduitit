from django import template

from core.service_launcher import (
    FEATURE_ICON_CLASS_FALLBACK,
    HOME_ICON_CLASS_FALLBACK,
    resolve_feature_icon_class,
    resolve_home_icon_class,
    resolve_ui_icon_class,
)


register = template.Library()


@register.filter
def product_icon_class(product, fallback=HOME_ICON_CLASS_FALLBACK):
    if hasattr(product, "icon") or hasattr(product, "launch_route_name"):
        return resolve_home_icon_class(product)
    return resolve_ui_icon_class(product, fallback=fallback)


@register.filter
def ui_icon_class(icon, fallback=HOME_ICON_CLASS_FALLBACK):
    return resolve_ui_icon_class(icon, fallback=fallback)


@register.filter
def feature_icon_class(feature, fallback=FEATURE_ICON_CLASS_FALLBACK):
    icon = getattr(feature, "icon", feature)
    return resolve_feature_icon_class(icon, fallback=fallback)
