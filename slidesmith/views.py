from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from products.models import Product

from .utils import build_slide_deck

SERVICE_TITLE = "초간단 PPT 만들기"
LEGACY_SERVICE_TITLES = ("수업 발표 메이커",)


def _get_service():
    product = Product.objects.filter(title=SERVICE_TITLE).first()
    if product:
        return product

    for legacy_title in LEGACY_SERVICE_TITLES:
        product = Product.objects.filter(title=legacy_title).first()
        if product:
            return product

    return Product.objects.filter(launch_route_name="slidesmith:main").first()


def _build_editor_context(request):
    title = request.POST.get("presentation_title") if request.method == "POST" else ""
    text = request.POST.get("presentation_text") if request.method == "POST" else ""
    deck = build_slide_deck(title, text)
    return {
        "service": _get_service(),
        "deck": deck,
        "presentation_title": deck["title"],
        "presentation_text": deck["text"],
        "template_cards": [
            {"key": "parent", "label": "학부모 설명회", "description": "학기 시작, 공개수업, 설명회 자료에 맞습니다."},
            {"key": "class", "label": "수업 안내", "description": "학생에게 활동 순서와 준비물을 설명할 때 좋습니다."},
            {"key": "meeting", "label": "회의 자료", "description": "교내 협의회나 업무 공유 발표에 맞는 흐름입니다."},
        ],
    }


@login_required
def main(request):
    return render(request, "slidesmith/main.html", _build_editor_context(request))


@login_required
def present(request):
    title = request.POST.get("presentation_title") if request.method == "POST" else request.GET.get("presentation_title")
    text = request.POST.get("presentation_text") if request.method == "POST" else request.GET.get("presentation_text")
    deck = build_slide_deck(title, text)
    return render(
        request,
        "slidesmith/present.html",
        {
            "service": _get_service(),
            "deck": deck,
        },
    )
