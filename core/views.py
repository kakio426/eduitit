from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from django.urls import NoReverseMatch
from products.models import Product, ServiceManual
from .forms import APIKeyForm, UserProfileUpdateForm
from .models import UserProfile, Post, Comment, Feedback, SiteConfig, ProductUsageLog
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone
from PIL import Image
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# V2 홈 목적별 섹션 매핑
# =============================================================================
PURPOSE_SECTIONS = [
    {
        'key': 'lesson',
        'title': '수업 준비',
        'subtitle': '수업을 더 풍성하게',
        'icon': 'fa-solid fa-book-open',
        'color': 'blue',
        'types': ['classroom'],
    },
    {
        'key': 'admin',
        'title': '문서·행정',
        'subtitle': '반복 업무를 줄여요',
        'icon': 'fa-solid fa-file-lines',
        'color': 'emerald',
        'types': ['work'],
    },
    {
        'key': 'consult',
        'title': '상담·진단',
        'subtitle': '학생을 더 깊이 이해해요',
        'icon': 'fa-solid fa-hand-holding-heart',
        'color': 'violet',
        'types': ['counsel'],
    },
    {
        'key': 'ai',
        'title': 'AI 생성·에듀테크',
        'subtitle': 'AI로 콘텐츠를 만들어요',
        'icon': 'fa-solid fa-wand-magic-sparkles',
        'color': 'cyan',
        'types': ['edutech', 'etc'],
    },
]


def get_purpose_sections(products_qs, preview_limit=None):
    """Product queryset → 목적별 섹션 + 게임 분리."""
    sections = []
    for sec in PURPOSE_SECTIONS:
        items = [p for p in products_qs if p.service_type in sec['types']]
        if items:
            if preview_limit and preview_limit > 0:
                preview_items = items[:preview_limit]
            else:
                preview_items = items
            overflow_items = items[len(preview_items):]
            remaining_count = max(0, len(items) - len(preview_items))
            sections.append({
                **sec,
                'products': preview_items,
                'overflow_products': overflow_items,
                'total_count': len(items),
                'remaining_count': remaining_count,
                'has_more': remaining_count > 0,
            })
    games = [p for p in products_qs if p.service_type == 'game']
    return sections, games


def _resolve_product_launch_url(product):
    """Resolve direct launch URL for quick actions."""
    if product.external_url:
        return product.external_url, True

    route_name = (product.launch_route_name or '').strip()
    if route_name:
        try:
            return reverse(route_name), False
        except NoReverseMatch:
            logger.warning("Launch route missing for product '%s' (%s).", product.title, route_name)

    return reverse('product_detail', kwargs={'pk': product.pk}), False


def _get_usage_based_quick_actions(user, product_list, limit=5):
    """사용 빈도 기반 퀵 액션 목록 생성. 기록 없으면 featured 기반 폴백."""
    from django.utils import timezone
    from datetime import timedelta

    since = timezone.now() - timedelta(days=14)
    usage_qs = (
        ProductUsageLog.objects
        .filter(user=user, created_at__gte=since, product__is_active=True)
        .values('product_id')
        .annotate(cnt=Count('product_id'))
        .order_by('-cnt')[:limit]
    )
    usage_ids = [row['product_id'] for row in usage_qs]
    product_map = {p.id: p for p in product_list}

    quick_actions = [product_map[pid] for pid in usage_ids if pid in product_map]

    # 사용 기록이 부족하면 featured → display_order 보충
    if len(quick_actions) < limit:
        seen = {p.id for p in quick_actions}
        for p in product_list:
            if p.is_featured and p.id not in seen:
                quick_actions.append(p)
                seen.add(p.id)
                if len(quick_actions) >= limit:
                    break
    if len(quick_actions) < limit:
        seen = {p.id for p in quick_actions}
        for p in product_list:
            if p.id not in seen:
                quick_actions.append(p)
                seen.add(p.id)
                if len(quick_actions) >= limit:
                    break

    return quick_actions


def _build_home_student_games_qr_context(request):
    """홈 화면에서 바로 사용할 학생 게임 QR 컨텍스트 생성."""
    if not request.user.is_authenticated:
        return {}

    from products.views import (
        _build_qr_data_url,
        _build_student_games_launch_url,
        _create_student_games_token,
        _student_games_max_age_seconds,
    )

    token = _create_student_games_token(request)
    launch_url = _build_student_games_launch_url(request, token)
    return {
        "student_games_launch_url": launch_url,
        "student_games_qr_data_url": _build_qr_data_url(launch_url),
        "student_games_expires_hours": max(1, _student_games_max_age_seconds() // 3600),
    }


def _build_today_context(request):
    """홈 V2용 오늘 할 일 위젯 데이터."""
    if not request.user.is_authenticated:
        return {"today_items": []}

    today = timezone.localdate()
    today_items = []

    try:
        from reservations.models import Reservation

        reservation_count = Reservation.objects.filter(
            room__school__owner=request.user,
            date=today,
        ).count()
        if reservation_count > 0:
            today_items.append(
                {
                    "title": "오늘 특별실 예약 확인",
                    "count_text": f"{reservation_count}건",
                    "description": "오늘 예약 현황을 확인하고 필요한 변경을 빠르게 처리하세요.",
                    "emoji": "🗓️",
                    "href": reverse("reservations:dashboard_landing"),
                    "cta_text": "예약 대시보드 열기",
                }
            )
    except Exception:
        logger.exception(
            "[TodayContext] reservations 집계 실패 user_id=%s",
            getattr(request.user, "id", None),
        )

    try:
        from collect.models import CollectionRequest

        collect_due_count = CollectionRequest.objects.filter(
            creator=request.user,
            status="active",
            deadline__isnull=False,
            deadline__date=today,
        ).count()
        if collect_due_count > 0:
            today_items.append(
                {
                    "title": "오늘 마감 수합 점검",
                    "count_text": f"{collect_due_count}건",
                    "description": "마감일이 오늘인 수합 요청이 있습니다. 미제출자를 확인해 주세요.",
                    "emoji": "📥",
                    "href": reverse("collect:dashboard"),
                    "cta_text": "수합 대시보드 열기",
                }
            )
    except Exception:
        logger.exception(
            "[TodayContext] collect 집계 실패 user_id=%s",
            getattr(request.user, "id", None),
        )

    try:
        from consent.models import SignatureRecipient, SignatureRequest

        unsigned_consent_count = SignatureRecipient.objects.filter(
            request__created_by=request.user,
            request__status=SignatureRequest.STATUS_SENT,
            status__in=[
                SignatureRecipient.STATUS_PENDING,
                SignatureRecipient.STATUS_VERIFIED,
            ],
        ).count()
        if unsigned_consent_count > 0:
            today_items.append(
                {
                    "title": "미서명 동의서 확인",
                    "count_text": f"{unsigned_consent_count}건",
                    "description": "서명이 아직 완료되지 않은 동의서가 있습니다. 진행 상태를 확인해 주세요.",
                    "emoji": "✍️",
                    "href": reverse("consent:dashboard"),
                    "cta_text": "동의서 대시보드 열기",
                }
            )
    except Exception:
        logger.exception(
            "[TodayContext] consent 집계 실패 user_id=%s",
            getattr(request.user, "id", None),
        )

    try:
        from classcalendar.models import CalendarEvent

        calendar_event_count = CalendarEvent.objects.filter(
            author=request.user,
            start_time__date=today,
        ).count()
        if calendar_event_count > 0:
            today_items.append(
                {
                    "title": "오늘 학급 일정",
                    "count_text": f"{calendar_event_count}건",
                    "description": "오늘 예정된 학급 일정이 있습니다. 캘린더를 확인해 보세요.",
                    "emoji": "📅",
                    "href": reverse("classcalendar:main"),
                    "cta_text": "캘린더 열기",
                }
            )
    except Exception:
        logger.exception(
            "[TodayContext] classcalendar 집계 실패 user_id=%s",
            getattr(request.user, "id", None),
        )

    return {
        "today_items": today_items,
        "today_date_text": today.strftime("%Y-%m-%d"),
    }


def _home_v2(request, products, posts, page_obj):
    """Feature flag on 시 호출되는 V2 홈."""
    product_list = list(products)
    sections, games = get_purpose_sections(product_list, preview_limit=2)

    if request.user.is_authenticated:
        UserProfile.objects.get_or_create(user=request.user)

        # 퀵 액션: 사용 빈도 기반 (폴백: featured → display_order)
        quick_actions = _get_usage_based_quick_actions(request.user, product_list)

        quick_action_items = []
        for product in quick_actions:
            href, is_external = _resolve_product_launch_url(product)
            quick_action_items.append({
                'product': product,
                'href': href,
                'is_external': is_external,
            })

        return render(request, 'core/home_authenticated_v2.html', {
            'products': products,
            'sections': sections,
            'games': games,
            'quick_actions': quick_action_items,
            'posts': posts,
            'page_obj': page_obj,
            **_build_today_context(request),
            **_build_home_student_games_qr_context(request),
        })

    featured_product = next((p for p in product_list if p.is_featured), product_list[0] if product_list else None)
    return render(request, 'core/home_v2.html', {
        'products': products,
        'featured_product': featured_product,
        'sections': sections,
        'games': games,
        'posts': posts,
        'page_obj': page_obj,
    })

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

    # 페이징 처리 (PC 우측 및 모바일 하단 SNS 위젯용)
    from django.core.paginator import Paginator
    paginator = Paginator(posts, 5) # 한 페이지에 5개씩
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # HTMX 요청이면 post_list 영역만 반환
    if request.headers.get('HX-Request') and request.GET.get('page'):
        return render(request, 'core/partials/post_list.html', {'posts': page_obj, 'page_obj': page_obj})

    # V2 홈: Feature flag on 시 분기
    if settings.HOME_V2_ENABLED:
        return _home_v2(request, products, page_obj, page_obj)

    # If user is logged in, show the "dashboard-style" authenticated home
    if request.user.is_authenticated:
        # Ensure profile exists to prevent 500 errors for legacy users
        UserProfile.objects.get_or_create(user=request.user)

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
            'posts': page_obj,
            'page_obj': page_obj
        })

    # Else show the public home
    featured_product = products.filter(is_featured=True).first()
    # Fallback if no featured product
    if not featured_product:
         featured_product = products.first()

    return render(request, 'core/home.html', {
        'products': products,
        'featured_product': featured_product,
        'posts': page_obj,
        'page_obj': page_obj
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
        
        from django.core.paginator import Paginator
        paginator = Paginator(posts, 5) # 등록 후에는 무조건 1페이지로
        page_obj = paginator.get_page(1)
        
        return render(request, 'core/partials/post_list.html', {'posts': page_obj, 'page_obj': page_obj})

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
        image = request.FILES.get('image')
        
        # 이미지 삭제 처리
        if request.POST.get('remove_image') == 'true':
            post.image = None
            
        # 이미지 수정 처리
        if image:
            MAX_SIZE = 10 * 1024 * 1024  # 10MB
            ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']

            if image.size > MAX_SIZE:
                messages.error(request, '이미지 크기는 10MB 이하만 가능합니다.')
                return render(request, 'core/partials/post_edit_form.html', {'post': post})

            if image.content_type not in ALLOWED_TYPES:
                messages.error(request, '허용되지 않는 파일 형식입니다. (JPEG, PNG, GIF, WebP만 가능)')
                return render(request, 'core/partials/post_edit_form.html', {'post': post})

            try:
                img = Image.open(image)
                img.verify()
                image.seek(0)
                post.image = image
            except Exception:
                messages.error(request, '올바른 이미지 파일이 아닙니다.')
                return render(request, 'core/partials/post_edit_form.html', {'post': post})

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
    from core.data import TOOLS_DATA
    from datetime import datetime, timedelta
    
    # Calculate is_new flag for each tool (updated within 30 days)
    today = datetime.now().date()
    threshold = today - timedelta(days=30)
    
    tools = []
    for tool in TOOLS_DATA:
        tool_copy = tool.copy()
        # Parse last_updated date (format: YYYY-MM-DD)
        try:
            updated_date = datetime.strptime(tool['last_updated'], '%Y-%m-%d').date()
            tool_copy['is_new'] = updated_date >= threshold
        except (KeyError, ValueError):
            tool_copy['is_new'] = False
        tools.append(tool_copy)
    
    return render(request, 'core/tool_guide.html', {
        'tools': tools,
        'tools_json': tools,
    })


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

@login_required
def update_email(request):
    """
    기존 사용자 이메일 및 닉네임 업데이트
    - 이메일이나 프로필 정보가 부족한 사용자에게 필무 정보 입력 요구
    """
    profile = request.user.userprofile
    
    # 이미 이메일과 닉네임이 모두 있으면 홈으로
    if request.user.email and profile.nickname and not profile.nickname.startswith('user'):
        return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        nickname = request.POST.get('nickname', '').strip()

        # 이메일 검증
        if not (email and '@' in email and '.' in email):
            messages.error(request, '올바른 이메일 주소를 입력해주세요.')
            return render(request, 'core/update_email.html', {'nickname': nickname, 'email': email})

        # 닉네임 검증
        if not nickname:
            messages.error(request, '사용하실 별명을 입력해주세요.')
            return render(request, 'core/update_email.html', {'nickname': nickname, 'email': email})

        # 정보 저장
        request.user.email = email
        request.user.first_name = nickname # SIS 표준: 이름 필드 채움
        request.user.save()
        
        profile.nickname = nickname
        profile.save()
        
        messages.success(request, f'{nickname}님, 환영합니다! 정보가 성공적으로 등록되었습니다. 🎉')

        # 원래 가려던 곳(next)이 있으면 그리로, 없으면 역할 선택 페이지(첫 가입 시)로
        next_url = request.GET.get('next')
        if not next_url or next_url == 'home':
            if not profile.role:
                return redirect('select_role')
            return redirect('home')
        return redirect(next_url)

    return render(request, 'core/update_email.html', {
        'nickname': profile.nickname if profile.nickname and not profile.nickname.startswith('user') else "",
        'email': request.user.email
    })

@login_required
def delete_account(request):
    """사용자 계정 탈퇴 처리"""
    if request.method == 'POST':
        user = request.user
        user.delete()
        messages.success(request, '그동안 이용해주셔서 감사합니다. 계정이 안전하게 삭제되었습니다.')
        return redirect('home')
    
    return render(request, 'core/delete_account.html')


@login_required
def admin_dashboard_view(request):
    """superuser 전용 방문자 통계 대시보드"""
    if not request.user.is_superuser:
        messages.error(request, '관리자만 접근 가능합니다.')
        return redirect('home')

    from .utils import get_visitor_stats, get_weekly_stats
    from .models import VisitorLog, SiteConfig
    from products.models import Product
    from django.utils import timezone
    import datetime
    import logging

    logger = logging.getLogger(__name__)

    # Handle NotebookLM URL update
    if request.method == 'POST' and 'notebook_manual_url' in request.POST:
        notebook_url = request.POST.get('notebook_manual_url', '').strip()
        
        # Validate URL (must be notebooklm.google.com or empty)
        if notebook_url and not notebook_url.startswith('https://notebooklm.google.com'):
            logger.warning(f"[NotebookLM_Config] Action: URL_UPDATE, Status: VALIDATION_FAILED, URL: {notebook_url}, User: {request.user.username}")
            messages.error(request, 'NotebookLM URL은 https://notebooklm.google.com 도메인이어야 합니다.')
        else:
            # Update Product instead of SiteConfig (SIS Compliance)
            product = Product.objects.filter(title='교사 백과사전').first()
            if product:
                old_url = product.external_url
                product.external_url = notebook_url
                product.save()
                logger.info(f"[NotebookLM_Config] Action: URL_UPDATE, Status: SUCCESS, Old_URL: {old_url}, New_URL: {notebook_url}, User: {request.user.username}")
                messages.success(request, 'NotebookLM 매뉴얼 URL이 성공적으로 업데이트되었습니다.')
            else:
                messages.error(request, '교사 백과사전 서비스를 찾을 수 없습니다. (ensure_notebooklm 실행 필요)')
        
        return redirect('admin_dashboard')

    today = timezone.localdate()
    
    # Total counts
    total_count = VisitorLog.objects.count()
    human_total_count = VisitorLog.objects.filter(is_bot=False).count()
    bot_total_count = total_count - human_total_count

    # Today's counts
    today_count = VisitorLog.objects.filter(visit_date=today).count()
    today_human_count = VisitorLog.objects.filter(visit_date=today, is_bot=False).count()
    today_bot_count = today_count - today_human_count

    # Weekly/Monthly start dates
    week_start = today - datetime.timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Weekly/Monthly counts
    week_count = VisitorLog.objects.filter(visit_date__gte=week_start).count()
    week_human_count = VisitorLog.objects.filter(visit_date__gte=week_start, is_bot=False).count()
    
    month_count = VisitorLog.objects.filter(visit_date__gte=month_start).count()
    month_human_count = VisitorLog.objects.filter(visit_date__gte=month_start, is_bot=False).count()

    # Detailed stats (Humans only for the chart)
    daily_stats = get_visitor_stats(30, exclude_bots=True)
    weekly_stats = get_weekly_stats(8, exclude_bots=True)

    # Chart max value
    max_daily = max((s['count'] for s in daily_stats), default=1) or 1
    
    # Get current NotebookLM URL from Product (SIS Compliance)
    notebook_product = Product.objects.filter(title='교사 백과사전').first()
    current_notebook_url = notebook_product.external_url if notebook_product else ''

    return render(request, 'core/admin_dashboard.html', {
        'today_count': today_count,
        'today_human_count': today_human_count,
        'today_bot_count': today_bot_count,
        'week_count': week_count,
        'week_human_count': week_human_count,
        'month_count': month_count,
        'month_human_count': month_human_count,
        'total_count': total_count,
        'human_total_count': human_total_count,
        'bot_total_count': bot_total_count,
        'daily_stats': daily_stats,
        'weekly_stats': weekly_stats,
        'max_daily': max_daily,
        'current_notebook_url': current_notebook_url,
    })


@require_POST
def feedback_view(request):
    """피드백 제출 (비로그인 사용자도 가능)"""
    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    category = request.POST.get('category', 'other')
    message_text = request.POST.get('message', '').strip()

    if not name or not message_text:
        messages.error(request, '이름과 내용은 필수 입력입니다.')
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '<div class="text-red-500 text-sm font-bold p-2">이름과 내용은 필수입니다.</div>',
                status=200,
            )
        return redirect('home')

    Feedback.objects.create(
        name=name,
        email=email,
        category=category if category in ('bug', 'suggestion', 'other') else 'other',
        message=message_text,
    )
    messages.success(request, '소중한 의견 감사합니다! 빠르게 확인하겠습니다.')

    if request.headers.get('HX-Request'):
        return HttpResponse(
            '<div class="text-green-600 text-sm font-bold p-2">감사합니다! 의견이 접수되었습니다.</div>',
            status=200,
        )
    return redirect('home')

def service_guide_list(request):
    """List of all available service manuals"""
    active_products_qs = Product.objects.filter(is_active=True).order_by('display_order')
    active_products_count = active_products_qs.count()
    manuals_all_qs = ServiceManual.objects.filter(product__is_active=True).select_related('product')
    manuals_qs = ServiceManual.objects.filter(
        is_published=True,
        product__is_active=True
    ).select_related('product').order_by('product__display_order')

    site_config = SiteConfig.load()
    featured_manuals = site_config.featured_manuals.filter(
        is_published=True,
        product__is_active=True
    ).select_related('product').order_by('product__display_order')

    featured_manual_ids = featured_manuals.values_list('id', flat=True)
    manuals = manuals_qs.exclude(id__in=featured_manual_ids)
    manual_count = manuals_qs.count()
    product_ids_with_any_manual = manuals_all_qs.values_list('product_id', flat=True)
    products_without_manual = active_products_qs.exclude(id__in=product_ids_with_any_manual)
    missing_manual_count = products_without_manual.count()

    return render(request, 'core/service_guide_list.html', {
        'manuals': manuals,
        'featured_manuals': featured_manuals,
        'products_without_manual': products_without_manual,
        'active_products_count': active_products_count,
        'manual_count': manual_count,
        'missing_manual_count': missing_manual_count,
    })

def service_guide_detail(request, pk):
    """Detailed view of a specific manual"""
    manual = get_object_or_404(
        ServiceManual.objects.select_related('product'), 
        pk=pk,
        is_published=True,
        product__is_active=True
    )
    sections = manual.sections.all()
    
    return render(request, 'core/service_guide_detail.html', {
        'manual': manual,
        'sections': sections
    })


@require_POST
def track_product_usage(request):
    """서비스 사용 기록 API (로그인 사용자 전용)."""
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'ignored'}, status=200)

    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid json'}, status=400)

    product_id = data.get('product_id')
    action = data.get('action', 'launch')
    source = data.get('source', 'other')

    if not product_id:
        return JsonResponse({'error': 'product_id required'}, status=400)

    valid_actions = [c[0] for c in ProductUsageLog.ACTION_CHOICES]
    valid_sources = [c[0] for c in ProductUsageLog.SOURCE_CHOICES]
    if action not in valid_actions:
        action = 'launch'
    if source not in valid_sources:
        source = 'other'

    try:
        product = Product.objects.get(pk=product_id, is_active=True)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'product not found'}, status=404)

    ProductUsageLog.objects.create(
        user=request.user,
        product=product,
        action=action,
        source=source,
    )
    return JsonResponse({'status': 'ok'})


@require_POST
@login_required
def set_active_classroom(request):
    """네비게이션 학급 단축키 — 세션에 현재 학급 저장."""
    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'invalid json'}, status=400)

    source = data.get('source', '')
    cid = data.get('classroom_id', '')

    # 선택 해제
    if not cid:
        request.session.pop('active_classroom_source', None)
        request.session.pop('active_classroom_id', None)
        return JsonResponse({'status': 'cleared'})

    if source == 'hs':
        try:
            from happy_seed.models import HSClassroom
            classroom = HSClassroom.objects.get(pk=cid, teacher=request.user)
        except Exception:
            return JsonResponse({'error': 'classroom not found'}, status=404)
        request.session['active_classroom_source'] = 'hs'
        request.session['active_classroom_id'] = str(classroom.pk)
        return JsonResponse({'status': 'ok', 'name': classroom.name})

    return JsonResponse({'error': 'unknown source'}, status=400)


def health_check(request):
    from django.db import connection
    try:
        connection.ensure_connection()
        return JsonResponse({'status': 'ok', 'db': 'connected'})
    except Exception as e:
        logger.exception("Health check DB connection failed: %s", e)
        return JsonResponse({'status': 'error', 'db': 'unavailable'}, status=503)
