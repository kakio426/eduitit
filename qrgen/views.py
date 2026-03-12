from django.shortcuts import render

from products.models import Product


def landing(request):
    service = Product.objects.filter(title='수업 QR 생성기').first()
    features = service.features.all() if service else []
    initial_url = (request.GET.get("url") or "").strip()
    initial_title = (request.GET.get("title") or "").strip()
    return render(
        request,
        'qrgen/landing.html',
        {
            'service': service,
            'features': features,
            'initial_url': initial_url,
            'initial_title': initial_title,
        },
    )
