from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.decorators import login_required
from products.models import Product
from .forms import APIKeyForm, UserProfileUpdateForm
from .models import UserProfile, Post
from django.contrib import messages
from django.db.models import Count

def home(request):
    # Order by display_order first, then by creation date
    products = Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
    
    # If user is logged in, show the "dashboard-style" authenticated home
    if request.user.is_authenticated:
        from django.db.models import Q
        # Get IDs of products explicitly owned by the user
        owned_ids = request.user.owned_products.values_list('product_id', flat=True)
        # Filter products that are either owned or free, and exclude specific ones
        available_products = products.filter(
            Q(id__in=owned_ids) | Q(price=0)
        ).exclude(
            Q(title__icontains="인사이트") | Q(title__icontains="사주")
        ).distinct()
        
        # SNS Posts
        posts = Post.objects.select_related('author', 'author__userprofile').prefetch_related('likes').all()
        
        return render(request, 'core/home_authenticated.html', {
            'products': available_products,
            'posts': posts
        })
    
    # Else show the public home
    featured_product = products.filter(is_featured=True).first() or products.first()
    return render(request, 'core/home.html', {
        'products': products,
        'featured_product': featured_product
    })

@login_required
def dashboard(request):
    return redirect('home')

@login_required
def post_create(request):
    if request.method == 'POST':
        content = request.POST.get('content')
        image = request.FILES.get('image')
        
        if content or image:
            Post.objects.create(
                author=request.user,
                content=content,
                image=image
            )
            
    # HTMX request check if needed, but for now redirecting or returning list could work. 
    # Ideally, for HTMX, we return the new list or the single new post.
    # To enable full refresh-less behavior, let's return the full list partial.
    if request.headers.get('HX-Request'):
        posts = Post.objects.select_related('author', 'author__userprofile').prefetch_related('likes').all()
        return render(request, 'core/partials/post_list.html', {'posts': posts})
        
    return redirect('home')

@login_required
def post_like(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.user in post.likes.all():
        post.likes.remove(request.user)
    else:
        post.likes.add(request.user)
        
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/post_item.html', {'post': post})
        
    return redirect('home')

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
    """역할 선택 및 별명 설정 화면"""
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    # 이미 역할과 닉네임이 설정된 경우 스킵 (단, 명시적으로 수정을 위해 접근했을 수도 있으니 처리 필요하지만, 
    # 보통 settings에서 수정하므로 여기는 초기 설정용으로 간주)
    # 하지만 사용자가 강제로 URL로 들어올 수도 있으므로, GET 요청이고 이미 설정되어있다면 home으로 보낸다.
    # 단, next가 있으면 next로 보낸다.
    if request.method == 'GET' and profile.role and profile.nickname:
        next_url = request.GET.get('next', 'home')
        return redirect(next_url)

    if request.method == 'POST':
        role = request.POST.get('role')
        nickname = request.POST.get('nickname')
        
        if role in ['school', 'instructor', 'company']:
            profile.role = role
        
        if nickname:
            profile.nickname = nickname.strip()

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

def policy_view(request):
    """이용약관 및 개인정보처리방침 페이지"""
    return render(request, 'core/policy.html')
