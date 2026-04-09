from django import template


register = template.Library()


def _normalize_ascii_canvas(value):
    lines = str(value or "").splitlines()
    if not lines:
        return []
    max_width = max(len(line) for line in lines)
    return [line.ljust(max_width) for line in lines]


@register.filter
def ascii_display_lines(value):
    return _normalize_ascii_canvas(value)
