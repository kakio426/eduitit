from django import template


register = template.Library()


@register.filter
def ascii_display_lines(value):
    return [line.strip() for line in str(value or "").splitlines()]
