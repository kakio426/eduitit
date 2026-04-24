from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from products.models import Product


PRIMARY_ACTIONS = (
    {
        "key": "viewer",
        "label": "보기",
        "route": "docviewer:main",
        "icon": "fa-solid fa-eye",
        "status": "확인",
    },
    {
        "key": "sign",
        "label": "사인",
        "route": "docsign:list",
        "icon": "fa-solid fa-file-signature",
        "status": "서명",
    },
    {
        "key": "consent",
        "label": "동의서",
        "route": "consent:dashboard",
        "icon": "fa-solid fa-clipboard-check",
        "status": "수합",
    },
    {
        "key": "textbook",
        "label": "교과서",
        "route": "textbooks:main",
        "icon": "fa-solid fa-book-open",
        "status": "수업",
    },
)

SECONDARY_ACTIONS = (
    {
        "key": "analysis",
        "label": "PDF 분석",
        "route": "textbook_ai:main",
        "icon": "fa-solid fa-magnifying-glass-chart",
        "status": "분석",
    },
    {
        "key": "register",
        "label": "서명부",
        "route": "signatures:list",
        "icon": "fa-solid fa-list-check",
        "status": "명단",
    },
    {
        "key": "versions",
        "label": "버전관리",
        "route": "version_manager:document_list",
        "icon": "fa-solid fa-code-compare",
        "status": "비교",
    },
)

NEXT_ACTIONS = (
    {"key": "merge", "label": "합치기", "icon": "fa-solid fa-object-group", "status": "준비 중"},
    {"key": "split", "label": "나누기", "icon": "fa-solid fa-scissors", "status": "준비 중"},
    {"key": "compress", "label": "압축", "icon": "fa-solid fa-compress", "status": "준비 중"},
)


def _with_href(action):
    payload = dict(action)
    payload["href"] = reverse(action["route"])
    return payload


@login_required
def main(request):
    product = Product.objects.filter(launch_route_name="pdfhub:main").order_by("id").first()
    context = {
        "product": product,
        "primary_actions": [_with_href(action) for action in PRIMARY_ACTIONS],
        "secondary_actions": [_with_href(action) for action in SECONDARY_ACTIONS],
        "next_actions": NEXT_ACTIONS,
    }
    return render(request, "pdfhub/main.html", context)
