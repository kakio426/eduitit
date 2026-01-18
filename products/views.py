from django.shortcuts import render, get_object_or_404
from .models import Product

def product_list(request):
    products = Product.objects.filter(is_active=True)
    return render(request, 'products/list.html', {'products': products})

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    is_owned = False
    if request.user.is_authenticated:
        is_owned = request.user.owned_products.filter(product=product).exists()
    return render(request, 'products/detail.html', {'product': product, 'is_owned': is_owned})
