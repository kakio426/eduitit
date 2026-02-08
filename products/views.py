from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Product

def product_list(request):
    products = Product.objects.filter(is_active=True)
    return render(request, 'products/list.html', {'products': products})

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    is_owned = False
    if request.user.is_authenticated:
        is_owned = request.user.owned_products.filter(product=product).exists() or product.price == 0
    return render(request, 'products/detail.html', {'product': product, 'is_owned': is_owned})

def product_preview(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    features = product.features.all()
    return render(request, 'products/partials/preview_modal.html', {
        'product': product,
        'features': features
    })

def yut_game(request):
    # 모바일 접근 체크
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(device in user_agent for device in ['mobile', 'android', 'iphone', 'ipad', 'ipod'])

    if is_mobile:
        return render(request, 'products/mobile_not_supported.html', {
            'service_name': '왁자지껄 교실 윷놀이',
            'reason': '윷놀이는 화면이 큰 데스크톱이나 태블릿 환경에 최적화되어 있습니다.',
            'suggestion': 'PC나 태블릿으로 접속해주세요!'
        })

    return render(request, 'products/yut_game.html')

def dutyticker_view(request):
    # 모바일 접근 체크
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(device in user_agent for device in ['mobile', 'android', 'iphone', 'ipad', 'ipod'])

    if is_mobile:
        return render(request, 'products/mobile_not_supported.html', {
            'service_name': '반짝반짝 우리반 알림판',
            'reason': '알림판은 교실 TV나 큰 화면에서 사용하도록 디자인되었습니다.',
            'suggestion': 'PC나 태블릿으로 접속해주세요!'
        })

    return render(request, 'products/dutyticker/main.html', {'hide_navbar': True})
