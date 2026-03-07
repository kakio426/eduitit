from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from products.models import Product

SERVICE_TITLE = "블록활동 실습실"
LEGACY_SERVICE_TITLES = ()


def _get_service():
    product = Product.objects.filter(title=SERVICE_TITLE).first()
    if product:
        return product

    for legacy_title in LEGACY_SERVICE_TITLES:
        product = Product.objects.filter(title=legacy_title).first()
        if product:
            return product

    return Product.objects.filter(launch_route_name="blockclass:main").first()


@login_required
def main(request):
    return render(
        request,
        "blockclass/main.html",
        {
            "service": _get_service(),
            "template_cards": [
                {"key": "sequence", "label": "순서 활동", "description": "안내 순서를 말풍선처럼 나누는 기본 흐름입니다."},
                {"key": "if", "label": "조건 활동", "description": "조건에 따라 다른 행동을 설명할 때 맞습니다."},
                {"key": "loop", "label": "반복 활동", "description": "같은 동작을 몇 번 되풀이하는 예시를 빠르게 보여줍니다."},
            ],
        },
    )
