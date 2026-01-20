from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from products.models import Product

def home(request):
    products = Product.objects.filter(is_active=True).order_by('-created_at')
    # Get one featured product for the hero card
    featured_product = Product.objects.filter(is_active=True, is_featured=True).first()
    # Fallback to the latest product if no featured one is set
    if not featured_product:
        featured_product = products.first()
        
    return render(request, 'core/home.html', {
        'products': products,
        'featured_product': featured_product
    })

@login_required
def dashboard(request):
    owned_items = request.user.owned_products.all()
    return render(request, 'core/dashboard.html', {'owned_items': owned_items})

def prompt_lab(request):
    return render(request, 'core/prompt_lab.html')

def tool_guide(request):
    return render(request, 'core/tool_guide.html')
