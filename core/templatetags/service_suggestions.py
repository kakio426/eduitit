from django import template

from core.suggestions import get_service_suggestions


register = template.Library()


@register.simple_tag
def load_service_suggestions(service_key):
    return get_service_suggestions(service_key)
