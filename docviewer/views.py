from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from products.models import Product

SERVICE_TITLE = "문서 미리보기실"
LEGACY_SERVICE_TITLES = ()


def _get_service():
    product = Product.objects.filter(title=SERVICE_TITLE).first()
    if product:
        return product

    for legacy_title in LEGACY_SERVICE_TITLES:
        product = Product.objects.filter(title=legacy_title).first()
        if product:
            return product

    return Product.objects.filter(launch_route_name="docviewer:main").first()


@login_required
def main(request):
    return render(
        request,
        "docviewer/main.html",
        {
            "service": _get_service(),
        },
    )
