import base64
import hashlib
import io
import logging
import secrets
import time
from urllib.parse import urlencode

import qrcode
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from core.seo import build_product_detail_seo
from core.product_visibility import filter_discoverable_products

from .dutyticker_scope import get_active_classroom_for_request, get_or_create_settings_for_scope
from .models import DTStudentGamesLaunchTicket, Product

logger = logging.getLogger(__name__)

STUDENT_GAMES_SESSION_MAX_AGE_SECONDS = 60 * 60 * 8
STUDENT_GAMES_LAUNCH_TICKET_TTL_SECONDS = 60 * 15
STUDENT_GAMES_SESSION_KEY = "dutyticker_student_games_mode"


def _student_games_mode_enabled(request):
    return bool(request.session.get(STUDENT_GAMES_SESSION_KEY))


def _student_games_session_max_age_seconds():
    configured = getattr(
        settings,
        "DUTYTICKER_STUDENT_GAMES_MAX_AGE_SECONDS",
        STUDENT_GAMES_SESSION_MAX_AGE_SECONDS,
    )
    try:
        configured = int(configured)
    except (TypeError, ValueError):
        configured = STUDENT_GAMES_SESSION_MAX_AGE_SECONDS
    return max(300, configured)


def _student_games_launch_ticket_ttl_seconds():
    configured = getattr(
        settings,
        "DUTYTICKER_STUDENT_GAMES_LAUNCH_TICKET_TTL_SECONDS",
        STUDENT_GAMES_LAUNCH_TICKET_TTL_SECONDS,
    )
    try:
        configured = int(configured)
    except (TypeError, ValueError):
        configured = STUDENT_GAMES_LAUNCH_TICKET_TTL_SECONDS
    return max(60, configured)


def _student_games_launch_ticket_ttl_minutes():
    return max(1, _student_games_launch_ticket_ttl_seconds() // 60)


def _hash_student_games_token(raw_token):
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def _issue_student_games_launch_ticket(request):
    classroom = get_active_classroom_for_request(request)
    now = timezone.now()
    DTStudentGamesLaunchTicket.objects.filter(
        issued_by=request.user,
        revoked_at__isnull=True,
        expires_at__gt=now,
    ).update(revoked_at=now)

    raw_token = secrets.token_urlsafe(24)
    ticket = DTStudentGamesLaunchTicket.objects.create(
        issued_by=request.user,
        classroom=classroom,
        token_hash=_hash_student_games_token(raw_token),
        expires_at=now + timezone.timedelta(seconds=_student_games_launch_ticket_ttl_seconds()),
    )
    return ticket, raw_token


def _find_valid_student_games_launch_ticket(raw_token):
    raw_token = (raw_token or "").strip()
    if not raw_token:
        return None
    token_hash = _hash_student_games_token(raw_token)

    try:
        ticket = DTStudentGamesLaunchTicket.objects.select_related("issued_by", "classroom").get(token_hash=token_hash)
    except DTStudentGamesLaunchTicket.DoesNotExist:
        return None

    now = timezone.now()
    if ticket.revoked_at is not None:
        return None
    if ticket.expires_at <= now:
        return None
    return ticket


def _student_games_catalog():
    return [
        {
            "emoji": "♟️",
            "title": "체스",
            "description": "말의 특성을 활용해 체크메이트를 노리는 전략 게임입니다.",
            "href": reverse("chess:play"),
        },
        {
            "emoji": "🧠",
            "title": "장기",
            "description": "초와 한이 번갈아 궁을 노리는 한국 전통 보드게임입니다.",
            "href": reverse("janggi:play"),
        },
        {
            "emoji": "🦁",
            "title": "동물 장기",
            "description": "작은 판에서 사자를 지키며 빠르게 수 읽기를 연습합니다.",
            "href": reverse("fairy_games:play", kwargs={"variant": "dobutsu"}),
        },
        {
            "emoji": "🟡",
            "title": "커넥트 포",
            "description": "칩 4개를 먼저 한 줄로 연결하면 승리합니다.",
            "href": reverse("fairy_games:play", kwargs={"variant": "cfour"}),
        },
        {
            "emoji": "🧱",
            "title": "이솔레이션",
            "description": "이동 후 칸을 막아 상대의 길을 끊는 차단형 게임입니다.",
            "href": reverse("fairy_games:play", kwargs={"variant": "isolation"}),
        },
        {
            "emoji": "⚔",
            "title": "아택스",
            "description": "복제와 점프로 돌을 늘려 판을 넓혀가는 점령 게임입니다.",
            "href": reverse("fairy_games:play", kwargs={"variant": "ataxx"}),
        },
        {
            "emoji": "🏁",
            "title": "브레이크스루",
            "description": "말을 끝줄까지 먼저 돌파시키는 레이스 전략 게임입니다.",
            "href": reverse("fairy_games:play", kwargs={"variant": "breakthrough"}),
        },
        {
            "emoji": "⚡",
            "title": "탭 순발력 챌린지",
            "description": "신호 뒤 가장 빠르게 탭해 반응속도를 겨룹니다.",
            "href": reverse("reflex_game:main"),
        },
        {
            "emoji": "🎲",
            "title": "교실 윷놀이",
            "description": "팀별로 윷을 던져 말판을 완주하는 협력 게임입니다.",
            "href": reverse("yut_game"),
        },
    ]


def _build_student_games_launch_url(request, token):
    path = reverse("dt_student_games_launch")
    query = urlencode({"token": token})
    return request.build_absolute_uri(f"{path}?{query}")


def _build_qr_data_url(raw_text):
    if not raw_text:
        return ""

    qr_image = qrcode.make(raw_text)
    with io.BytesIO() as buffer:
        qr_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _is_phone_user_agent(user_agent):
    """
    Return True only for phone-class devices.
    iPad/tablet should be allowed for large-screen services.
    """
    ua = (user_agent or '').lower()

    if 'iphone' in ua or 'ipod' in ua:
        return True

    # Android phone UAs usually include both 'android' and 'mobile'.
    if 'android' in ua and 'mobile' in ua:
        return True

    # Generic fallback: treat explicit mobile UAs as phone, exclude tablet keywords.
    if 'mobile' in ua and 'ipad' not in ua and 'tablet' not in ua:
        return True

    return False


def _is_force_desktop(request):
    """Allow user to bypass phone block intentionally via query string."""
    return request.GET.get('force_desktop', '').lower() in ('1', 'true', 'yes')


def _should_block_for_large_screen_service(request):
    """
    Return True if request should be blocked on phone-size devices.
    Tablet blocking can be toggled with ALLOW_TABLET_ACCESS.
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    ua = user_agent.lower()

    if _is_force_desktop(request):
        logger.info("Large-screen service bypass via force_desktop query.")
        return False

    if _is_phone_user_agent(user_agent):
        logger.info("Large-screen service blocked for phone user agent.")
        return True

    allow_tablet_access = getattr(settings, 'ALLOW_TABLET_ACCESS', True)
    if not allow_tablet_access and ('ipad' in ua or 'tablet' in ua):
        logger.info("Large-screen service blocked for tablet (ALLOW_TABLET_ACCESS=False).")
        return True

    return False


def product_list(request):
    from core.views import (
        CATALOG_SCENARIO_SECTIONS,
        _attach_product_launch_meta,
        _build_catalog_hub_context,
        _build_catalog_scenario_sections,
        _is_sheetbook_cross_surface_hidden,
        _normalize_catalog_section_key,
    )

    products = filter_discoverable_products(
        Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
    )
    product_list = _attach_product_launch_meta(list(products))
    surface_products = [product for product in product_list if not _is_sheetbook_cross_surface_hidden(product)]
    selected_section_key = _normalize_catalog_section_key(request.GET.get('section'))
    scenario_sections = _build_catalog_scenario_sections(
        surface_products,
        selected_section_key=selected_section_key,
    )
    if not scenario_sections:
        selected_section_key = ''
        scenario_sections = _build_catalog_scenario_sections(surface_products)
    selected_scenario_section = next(
        (section for section in CATALOG_SCENARIO_SECTIONS if section["key"] == selected_section_key),
        None,
    )
    return render(
        request,
        'products/list.html',
        {
            'products': surface_products,
            'catalog_hub': _build_catalog_hub_context(surface_products),
            'scenario_sections': scenario_sections,
            'selected_scenario_section': selected_scenario_section,
            'total_count': len(surface_products),
        },
    )

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    is_owned = False
    if request.user.is_authenticated:
        is_owned = request.user.owned_products.filter(product=product).exists() or product.price == 0
    from core.views import _resolve_product_launch_url
    launch_href, launch_is_external = _resolve_product_launch_url(product)
    can_launch = bool(launch_href) and launch_href != request.path
    seo_meta = build_product_detail_seo(request, product)
    response = render(request, 'products/detail.html', {
        'product': product,
        'is_owned': is_owned,
        'launch_href': launch_href,
        'launch_is_external': launch_is_external,
        'can_launch': can_launch,
        **seo_meta.as_context(),
    })
    if seo_meta.robots.startswith("noindex"):
        response["X-Robots-Tag"] = seo_meta.robots.replace(",", ", ")
    return response

def product_preview(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    features = product.features.all()
    from core.views import _attach_product_launch_meta, _resolve_product_launch_url
    product = _attach_product_launch_meta([product])[0]
    launch_href, launch_is_external = _resolve_product_launch_url(product)
    return render(request, 'products/partials/preview_modal.html', {
        'product': product,
        'features': features,
        'launch_href': launch_href,
        'launch_is_external': launch_is_external,
    })

def yut_game(request):
    # 모바일 접근 체크
    is_mobile = _should_block_for_large_screen_service(request)

    if is_mobile:
        return render(request, 'products/mobile_not_supported.html', {
            'service_name': '왁자지껄 교실 윷놀이',
            'reason': '윷놀이는 화면이 큰 데스크톱이나 태블릿 환경에 최적화되어 있습니다.',
            'suggestion': 'PC나 태블릿으로 접속해주세요!',
            'continue_url': f'{request.path}?force_desktop=1',
        })

    return render(
        request,
        'products/yut_game.html',
        {'hide_navbar': _student_games_mode_enabled(request)},
    )

@ensure_csrf_cookie
def dutyticker_view(request):
    # 모바일 접근 체크
    is_mobile = _should_block_for_large_screen_service(request)

    if is_mobile:
        return render(request, 'products/mobile_not_supported.html', {
            'service_name': '반짝반짝 우리반 알림판',
            'reason': '알림판은 교실 TV나 큰 화면에서 사용하도록 디자인되었습니다.',
            'suggestion': 'PC나 태블릿으로 접속해주세요!',
            'continue_url': f'{request.path}?force_desktop=1',
        })

    context = {
        'hide_navbar': True,
        'initial_theme': 'deep_space',
    }
    if request.user.is_authenticated:
        classroom = get_active_classroom_for_request(request)
        dt_settings, _ = get_or_create_settings_for_scope(request.user, classroom)
        context.update(
            {
                "student_games_issue_url": reverse("dt_student_games_issue"),
                "student_games_launch_ttl_minutes": _student_games_launch_ticket_ttl_minutes(),
                "initial_theme": dt_settings.theme or "deep_space",
            }
        )

    return render(request, 'products/dutyticker/main.html', context)


@require_POST
def dutyticker_student_games_issue(request):
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "로그인이 필요합니다."}, status=401)

    _, raw_token = _issue_student_games_launch_ticket(request)
    launch_url = _build_student_games_launch_url(request, raw_token)
    return JsonResponse(
        {
            "success": True,
            "launch_url": launch_url,
            "qr_data_url": _build_qr_data_url(launch_url),
            "expires_in_minutes": _student_games_launch_ticket_ttl_minutes(),
        }
    )


def dutyticker_student_games_launch(request):
    token = (request.GET.get("token") or "").strip()
    ticket = _find_valid_student_games_launch_ticket(token)
    if not ticket:
        return render(
            request,
            "products/dutyticker/student_games_invalid.html",
            {
                "hide_navbar": True,
                "student_games_invalid_message": "링크가 만료되었거나 새 링크로 교체되었습니다. 선생님께 새 QR을 요청하세요.",
            },
            status=403,
        )

    request.session[STUDENT_GAMES_SESSION_KEY] = {
        "issuer_id": ticket.issued_by_id,
        "classroom_id": ticket.classroom_id,
        "enabled_at": int(time.time()),
    }
    request.session.set_expiry(_student_games_session_max_age_seconds())
    request.session.modified = True

    return redirect("dt_student_games_portal")


def dutyticker_student_games_portal(request):
    if not _student_games_mode_enabled(request):
        return redirect("home")

    return render(
        request,
        "products/dutyticker/student_games_portal.html",
        {
            "hide_navbar": True,
            "games": _student_games_catalog(),
        },
    )


def dutyticker_student_games_exit(request):
    request.session.pop(STUDENT_GAMES_SESSION_KEY, None)
    request.session.modified = True
    return redirect("home")
