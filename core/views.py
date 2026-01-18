from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from products.models import Product

def home(request):
    featured_products = Product.objects.filter(is_active=True)[:3]
    return render(request, 'core/home.html', {'products': featured_products})

@login_required
def dashboard(request):
    owned_items = request.user.owned_products.all()
    return render(request, 'core/dashboard.html', {'owned_items': owned_items})
