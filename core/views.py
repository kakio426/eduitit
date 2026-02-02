from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from products.models import Product
from .forms import APIKeyForm, UserProfileUpdateForm
from .models import UserProfile, Post, Comment
from django.contrib import messages
from django.db.models import Count
from PIL import Image

def home(request):
    # Order by display_order first, then by creation date
    products = Product.objects.filter(is_active=True).order_by('display_order', '-created_at')

    # SNS Posts - 모든 사용자에게 제공 (최신순 정렬)
    posts = Post.objects.select_related(
        'author',
        'author__userprofile'
    ).prefetch_related(
        'likes',
        'comments',
        'comments__author',
        'comments__author__userprofile'
    ).annotate(
        likes_count_annotated=Count('likes', distinct=True),
        comments_count_annotated=Count('comments', distinct=True)
    ).order_by('-created_at')

    # If user is logged in, show the "dashboard-style" authenticated home
    if request.user.is_authenticated:
        # Ensure profile exists to prevent 500 errors for legacy users
        if not hasattr(request.user, 'userprofile'):
            UserProfile.objects.create(user=request.user)

        from django.db.models import Q
        # Get IDs of products explicitly owned by the user
        owned_ids = request.user.owned_products.values_list('product_id', flat=True)
        # Filter products that are either owned or free, and exclude specific ones
        available_products = products.filter(
            Q(id__in=owned_ids) | Q(price=0)
        ).exclude(
            Q(title__icontains="인사이트") | Q(title__icontains="사주")
        ).distinct()

        return render(request, 'core/home_authenticated.html', {
            'products': available_products,
            'posts': posts
        })

    # Else show the public home
    featured_product = products.filter(is_featured=True).first() or products.first()
    return render(request, 'core/home.html', {
        'products': products,
        'featured_product': featured_product,
        'posts': posts
    })

@login_required
def dashboard(request):
    return redirect('home')

@login_required
def post_create(request):
    if request.method == 'POST':
        content = request.POST.get('content')
        image = request.FILES.get('image')

        # 이미지 검증
        if image:
            MAX_SIZE = 10 * 1024 * 1024  # 10MB
            ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

            if image.size > MAX_SIZE:
                messages.error(request, '이미지 크기는 10MB 이하만 가능합니다.')
                return redirect('home')

            if image.content_type not in ALLOWED_TYPES:
                messages.error(request, '허용되지 않는 파일 형식입니다. (JPEG, PNG, GIF, WebP만 가능)')
                return redirect('home')

            # PIL로 이미지 무결성 검증 (악성 파일 방지)
            try:
                img = Image.open(image)
                img.verify()
                image.seek(0)  # 포인터 리셋
            except Exception:
                messages.error(request, '올바른 이미지 파일이 아닙니다.')
                return redirect('home')

        # 게시물 생성
        if content or image:
            Post.objects.create(
                author=request.user,
                content=content,
                image=image
            )

    # HTMX 응답
    if request.headers.get('HX-Request'):
        posts = Post.objects.select_related(
            'author',
            'author__userprofile'
        ).prefetch_related(
            'likes',
            'comments',
            'comments__author',
            'comments__author__userprofile'
        ).annotate(
            likes_count_annotated=Count('likes', distinct=True),
            comments_count_annotated=Count('comments', distinct=True)
        ).order_by('-created_at')
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

@login_required
def comment_create(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Comment.objects.create(
                post=post,
                author=request.user,
                content=content
            )
            
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/post_item.html', {'post': post})
        
    return redirect('home')

@login_required
def post_delete(request, pk):
    post = get_object_or_404(Post, pk=pk)
    # Check if the user is the author or staff
    if post.author == request.user or request.user.is_staff:
        post.delete()
        if request.headers.get('HX-Request'):
            return HttpResponse("") # HTMX expects empty string for deletion
            
    return redirect('home')

@login_required
def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)
    
    # Only author can edit
    if post.author != request.user:
        return HttpResponse("Unauthorized", status=403)
        
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            post.content = content
            post.save()
            # Return the updated post item (expanded)
            return render(request, 'core/partials/post_item.html', {'post': post, 'is_first': True})
            
    # GET: Return the edit form
    return render(request, 'core/partials/post_edit_form.html', {'post': post})

@login_required
def post_detail_partial(request, pk):
    """Helper view to return the read-only post item (e.g. for Cancel button)"""
    post = get_object_or_404(Post, pk=pk)
    # Force expansion when returning from edit mode
    return render(request, 'core/partials/post_item.html', {'post': post, 'is_first': True})

@login_required
def comment_delete(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    # Check if the user is the author or staff
    if comment.author == request.user or request.user.is_staff:
        comment.delete()
        if request.headers.get('HX-Request'):
            return HttpResponse("") # HTMX expects empty string
            
    return redirect('home')

@login_required
def comment_edit(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    
    # Only author can edit
    if comment.author != request.user:
        return HttpResponse("Unauthorized", status=403)
        
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            comment.content = content
            comment.save()
            return render(request, 'core/partials/comment_item.html', {'comment': comment})
            
    # GET: Return the edit form
    return render(request, 'core/partials/comment_edit_form.html', {'comment': comment})

@login_required
def comment_item_partial(request, pk):
    """Helper view to return the read-only comment item"""
    comment = get_object_or_404(Comment, pk=pk)
    return render(request, 'core/partials/comment_item.html', {'comment': comment})

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
