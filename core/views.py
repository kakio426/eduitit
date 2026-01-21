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
    from django.db.models import Q
    # Get IDs of products explicitly owned by the user
    owned_ids = request.user.owned_products.values_list('product_id', flat=True)
    # Filter products that are either owned or free
    available_products = Product.objects.filter(
        Q(id__in=owned_ids) | Q(price=0),
        is_active=True
    ).order_by('display_order', '-created_at').distinct()
    
    return render(request, 'core/dashboard.html', {'products': available_products})

def prompt_lab(request):
    return render(request, 'core/prompt_lab.html')

def tool_guide(request):
    return render(request, 'core/tool_guide.html')

def about(request):
    # Stats could be dynamic later
    stats = {
        'lecture_hours': 120, # Placeholder
        'tools_built': Product.objects.count() + 5, # Approx
        'students': 500, # Placeholder
    }
    return render(request, 'core/about.html', {'stats': stats})
