import base64
import io
import logging
import time
from urllib.parse import urlencode

import qrcode
from django.conf import settings
from django.core import signing
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Product

logger = logging.getLogger(__name__)

STUDENT_GAMES_TOKEN_SALT = "dutyticker.student_games.v1"
STUDENT_GAMES_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 8
STUDENT_GAMES_SESSION_KEY = "dutyticker_student_games_mode"


def _student_games_mode_enabled(request):
    return bool(request.session.get(STUDENT_GAMES_SESSION_KEY))


def _student_games_max_age_seconds():
    configured = getattr(settings, "DUTYTICKER_STUDENT_GAMES_MAX_AGE_SECONDS", STUDENT_GAMES_TOKEN_MAX_AGE_SECONDS)
    try:
        configured = int(configured)
    except (TypeError, ValueError):
        configured = STUDENT_GAMES_TOKEN_MAX_AGE_SECONDS
    return max(300, configured)


def _create_student_games_token(request):
    payload = {
        "v": 1,
        "issued_at": int(time.time()),
        "issuer_id": request.user.id if request.user.is_authenticated else None,
    }
    return signing.dumps(payload, salt=STUDENT_GAMES_TOKEN_SALT, compress=True)


def _verify_student_games_token(token):
    if not token:
        return None

    try:
        payload = signing.loads(
            token,
            salt=STUDENT_GAMES_TOKEN_SALT,
            max_age=_student_games_max_age_seconds(),
        )
    except (signing.BadSignature, signing.SignatureExpired):
        return None

    if not isinstance(payload, dict) or payload.get("v") != 1:
        return None
    return payload


def _student_games_catalog():
    return [
        {
            "emoji": "♟️",
            "title": "체스",
            "description": "2인 대결 또는 AI 대결로 전략을 익혀요.",
            "href": reverse("chess:play"),
        },
        {
            "emoji": "🧠",
            "title": "장기",
            "description": "한국식 보드게임으로 수 읽기 훈련을 해요.",
            "href": reverse("janggi:play"),
        },
        {
            "emoji": "🛡️",
            "title": "전략 게임 5종",
            "description": "격리/브레이크스루 등 로컬 대결 모음이에요.",
            "href": reverse("fairy_games:index"),
        },
        {
            "emoji": "🎲",
            "title": "교실 윷놀이",
            "description": "쉬는 시간 팀전으로 분위기를 살려요.",
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
    products = Product.objects.filter(is_active=True)
    return render(request, 'products/list.html', {'products': products})

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    is_owned = False
    if request.user.is_authenticated:
        is_owned = request.user.owned_products.filter(product=product).exists() or product.price == 0
    from core.views import _resolve_product_launch_url
    launch_href, launch_is_external = _resolve_product_launch_url(product)
    can_launch = bool(launch_href) and launch_href != request.path
    return render(request, 'products/detail.html', {
        'product': product,
        'is_owned': is_owned,
        'launch_href': launch_href,
        'launch_is_external': launch_is_external,
        'can_launch': can_launch,
    })

def product_preview(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    features = product.features.all()
    from core.views import _resolve_product_launch_url
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

    context = {'hide_navbar': True}
    if request.user.is_authenticated:
        token = _create_student_games_token(request)
        launch_url = _build_student_games_launch_url(request, token)
        context.update(
            {
                "student_games_launch_url": launch_url,
                "student_games_qr_data_url": _build_qr_data_url(launch_url),
                "student_games_expires_hours": max(1, _student_games_max_age_seconds() // 3600),
            }
        )

    return render(request, 'products/dutyticker/main.html', context)


def dutyticker_student_games_launch(request):
    token = (request.GET.get("token") or "").strip()
    payload = _verify_student_games_token(token)
    if not payload:
        return render(
            request,
            "products/dutyticker/student_games_invalid.html",
            {"hide_navbar": True},
            status=403,
        )

    request.session[STUDENT_GAMES_SESSION_KEY] = {
        "issuer_id": payload.get("issuer_id"),
        "enabled_at": int(time.time()),
    }
    request.session.set_expiry(_student_games_max_age_seconds())
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
