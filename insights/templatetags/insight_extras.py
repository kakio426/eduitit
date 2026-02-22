import re

from django import template


register = template.Library()


@register.filter
def parse_tags(value):
    """Return normalized hashtag list from comma/newline separated text."""
    if not value:
        return []

    tokens = re.split(r"[,\n]+", str(value))
    results = []
    seen = set()

    for token in tokens:
        cleaned = token.strip()
        if not cleaned:
            continue
        if not cleaned.startswith("#"):
            cleaned = f"#{cleaned}"
        cleaned = cleaned.rstrip(".,;:")
        if cleaned in seen:
            continue
        seen.add(cleaned)
        results.append(cleaned)

    return results
