from django.shortcuts import render, redirect, reverse
from django.contrib.auth.decorators import login_required
from products.models import Product
from .forms import APIKeyForm, UserProfileUpdateForm
from .models import UserProfile
from django.contrib import messages

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
    # Filter products that are either owned or free, and exclude specific ones
    available_products = Product.objects.filter(
        Q(id__in=owned_ids) | Q(price=0),
        is_active=True
    ).exclude(
        Q(title__icontains="인사이트") | Q(title__icontains="사주")
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

@login_required
def settings_view(request):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, '프로필 정보가 성공적으로 수정되었습니다.')
            return redirect('settings')
    else:
        form = UserProfileUpdateForm(instance=profile)
    
    return render(request, 'core/settings.html', {'form': form})

@login_required
def select_role(request):
    """역할 선택 화면 (학교, 강사, 업체)"""
    if request.method == 'POST':
        role = request.POST.get('role')
        if role in ['school', 'instructor', 'company']:
            profile = request.user.userprofile
            profile.role = role
            profile.save()
            # 역할 선택 후 원래 가려던 SSO 페이지로 이동하거나 대시보드로 이동
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
    
    return render(request, 'core/select_role.html')

@login_required
def sso_to_schoolit(request):
    """스쿨잇으로 자동 로그인하여 이동하는 브릿지 뷰"""
    from .utils import generate_sso_token, get_schoolit_url
    
    profile = request.user.userprofile
    if not profile.role:
        # 역할이 없으면 선택 페이지로 먼저 보냄
        return redirect(f"{reverse('select_role')}?next={request.path}")
    
    token = generate_sso_token(request.user)
    target_url = get_schoolit_url(profile.role)
    
    # 쿼리 스트링으로 토큰 전달 (schoolit에서 이 토큰을 받아 처리해야 함)
    import urllib.parse
    redirect_url = f"{target_url}?sso_token={token}"
    return redirect(redirect_url)
