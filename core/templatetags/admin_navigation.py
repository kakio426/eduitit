from django import template

from core.admin_navigation import build_admin_navigation


register = template.Library()


@register.simple_tag(takes_context=True)
def get_admin_navigation(context, app_list):
    request = context.get("request")
    current_path = getattr(request, "path", "")
    return build_admin_navigation(app_list, current_path=current_path)
