from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_sameorigin

from products.models import Product

from classcalendar.views import build_message_capture_ui_context


SERVICE_ROUTE = "messagebox:main"


@login_required
@xframe_options_sameorigin
def main_view(request):
    service = Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
    message_capture_ui = build_message_capture_ui_context(request.user)
    initial_capture_id = str(request.GET.get("capture") or "").strip()
    context = {
        "service": service,
        "title": service.title if service else "업무 메시지 보관함",
        "page_title": (service.title if service else "업무 메시지 보관함"),
        "page_subtitle": "교육청 메신저 등에서 받은 중요한 메시지를 붙여넣고, 필요하면 일정에 연결해 나중에 다시 보세요.",
        "message_capture_enabled": message_capture_ui["enabled"],
        "message_capture_item_types_enabled": message_capture_ui["item_types_enabled"],
        "message_capture_limits_json": message_capture_ui["limits"],
        "message_capture_urls_json": message_capture_ui["urls"],
        "initial_capture_id": initial_capture_id,
        "calendar_main_url": reverse("calendar_main"),
    }
    return render(request, "messagebox/main.html", context)
