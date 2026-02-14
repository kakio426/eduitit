import re

from django import template


register = template.Library()


@register.filter
def clean_manual_text(value):
    """Remove markdown markers for plain-text manual rendering."""
    text = str(value or "")
    text = text.replace("\r\n", "\n")
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    text = text.replace("`", "")
    return text
