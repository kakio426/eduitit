from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from products.models import Product

def home(request):
    # Order by display_order first, then by creation date
    products = Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
    # Get the featured product with lowest display_order (highest priority)
    featured_product = Product.objects.filter(is_active=True, is_featured=True).order_by('display_order').first()
    # Fallback to the product with lowest display_order if no featured one is set
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
