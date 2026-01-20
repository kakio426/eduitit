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
    return render(request, 'products/yut_game.html')
