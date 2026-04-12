import base64
import hashlib
import io
import logging
import secrets
import time
from urllib.parse import urlencode

import qrcode
from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import strip_tags
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from core.guide_links import SERVICE_GUIDE_PADLET_URL
from core.seo import build_product_detail_seo, build_product_list_page_seo, build_route_page_seo
from core.product_visibility import filter_discoverable_products

from .dutyticker_scope import apply_classroom_scope, get_active_classroom_for_request, get_or_create_settings_for_scope
from .models import DTStudentGamesLaunchTicket, DTSchedule, Product, ServiceManual
from .tts_announcement import (
    annotate_tts_rows,
    build_demo_tts_rows,
    build_tts_announcement_rows,
    build_tts_broadcast_template_groups,
)

logger = logging.getLogger(__name__)

STUDENT_GAMES_SESSION_MAX_AGE_SECONDS = 60 * 60 * 8
STUDENT_GAMES_LAUNCH_TICKET_TTL_SECONDS = 60 * 15
STUDENT_GAMES_SESSION_KEY = "dutyticker_student_games_mode"
STUDENT_GAMES_UNAVAILABLE_MESSAGE = (
    "학생 게임 입장 기능을 아직 준비하지 못했습니다. 잠시 후 다시 시도해 주세요."
)

PRODUCT_DETAIL_AUDIENCE_BY_ROUTE = {
    "collect:landing": "가정통신문 뒤 응답, 파일, 링크를 한 번에 모아야 하는 교사에게 맞는 도구입니다.",
    "consent:landing": "학부모 동의서를 링크로 회수하고 보관까지 정리해야 하는 교사에게 맞는 도구입니다.",
    "handoff:landing": "배부 누락 없이 수령 현황을 빠르게 끝내고 싶은 교사에게 맞는 도구입니다.",
    "noticegen:main": "알림장과 가정 안내 문구를 짧은 시간 안에 정리해야 하는 교사에게 맞는 도구입니다.",
    "happy_seed:dashboard": "긍정 행동 기록과 보상을 학급 루틴으로 운영하고 싶은 교사에게 맞는 도구입니다.",
    "happy_seed:landing": "긍정 행동 기록과 보상을 학급 루틴으로 운영하고 싶은 교사에게 맞는 도구입니다.",
    "reservations:landing": "특별실 예약이 겹치지 않도록 시간표를 조정해야 하는 교사에게 맞는 도구입니다.",
    "reservations:dashboard_landing": "특별실 예약이 겹치지 않도록 시간표를 조정해야 하는 교사에게 맞는 도구입니다.",
    "schoolprograms:landing": "지역과 주제로 학교로 찾아오는 프로그램을 비교하고 바로 문의하려는 교사에게 맞는 도구입니다.",
    "tts_announce": "학생들에게 안내, 집중 신호, 정리 멘트를 바로 읽어 줘야 하는 교사에게 맞는 도구입니다.",
}

PRODUCT_DETAIL_AUDIENCE_BY_TYPE = {
    "collect_sign": "안내 뒤 회수와 확인을 한 번에 끝내고 싶은 교사에게 맞는 도구입니다.",
    "classroom": "오늘 수업과 학급 운영을 더 매끄럽게 돌리고 싶은 교사에게 맞는 도구입니다.",
    "work": "문서 준비와 정리를 짧은 시간 안에 끝내고 싶은 교사에게 맞는 도구입니다.",
    "game": "교실 분위기를 빠르게 살릴 활동이 필요한 교사에게 맞는 도구입니다.",
    "counsel": "상담과 학생 이해를 부드럽게 이어가고 싶은 교사에게 맞는 도구입니다.",
    "edutech": "막힐 때 참고할 가이드와 인사이트가 필요한 교사에게 맞는 도구입니다.",
    "etc": "필요한 기능을 찾자마자 바로 써보고 싶은 교사에게 맞는 도구입니다.",
}

PUBLIC_PREVIEW_ACCESS_LABELS = {"공개 체험", "미리보기 가능", "외부 이동"}


def _student_games_mode_enabled(request):
    return bool(request.session.get(STUDENT_GAMES_SESSION_KEY))


def _clean_detail_text(value):
    return " ".join(strip_tags(str(value or "")).split()).strip()


def _summarize_detail_text(value, *, limit=100):
    text = _clean_detail_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _safe_media_url(file_field):
    if not file_field:
        return ""
    try:
        return file_field.url or ""
    except ValueError:
        return ""


def _build_product_value_proposition(product):
    public_name = getattr(product, "public_service_name", "") or getattr(product, "title", "") or "이 서비스"
    for candidate in (
        getattr(product, "lead_text", ""),
        getattr(product, "teacher_first_support_label", ""),
        getattr(product, "home_card_summary", ""),
        getattr(product, "solve_text", ""),
        getattr(product, "description", ""),
    ):
        summary = _clean_detail_text(candidate)
        if summary and summary != public_name:
            return summary
    return f"{public_name} 사용 흐름을 빠르게 시작할 수 있습니다."


def _build_product_audience_copy(product):
    route_name = str(getattr(product, "launch_route_name", "") or "").strip().lower()
    service_type = str(getattr(product, "service_type", "") or "").strip()
    return (
        PRODUCT_DETAIL_AUDIENCE_BY_ROUTE.get(route_name)
        or PRODUCT_DETAIL_AUDIENCE_BY_TYPE.get(service_type)
        or PRODUCT_DETAIL_AUDIENCE_BY_TYPE["etc"]
    )


def _build_product_access_copy(product):
    override_copy = str(getattr(product, "product_access_copy_override", "") or "").strip()
    if override_copy:
        return override_copy

    access_label = str(getattr(product, "home_access_status_label", "") or "").strip()
    if access_label in PUBLIC_PREVIEW_ACCESS_LABELS:
        return "로그인 없이도 핵심 흐름을 먼저 확인할 수 있습니다."
    return "교사 계정으로 로그인한 뒤 바로 이어서 시작합니다."


def _build_product_detail_steps(product, manual, features):
    steps = []
    if manual is not None:
        for section in manual.sections.all():
            title = _clean_detail_text(section.title)
            if not title:
                continue
            description = _summarize_detail_text(section.content, limit=88) or "핵심 흐름을 순서대로 확인합니다."
            steps.append({"title": title, "description": description})
            if len(steps) >= 3:
                return steps

    for feature in features:
        title = _clean_detail_text(feature.title)
        if not title:
            continue
        description = _summarize_detail_text(feature.description, limit=88) or "핵심 기능을 바로 확인합니다."
        steps.append({"title": title, "description": description})
        if len(steps) >= 3:
            return steps

    fallback_specs = [
        (
            "무엇을 해결하나요",
            getattr(product, "solve_text", "") or getattr(product, "description", ""),
        ),
        (
            "어떻게 시작하나요",
            getattr(product, "lead_text", "") or getattr(product, "teacher_first_support_label", ""),
        ),
        (
            "어떤 결과가 남나요",
            getattr(product, "result_text", "") or "핵심 결과를 바로 확인하고 이어서 정리할 수 있습니다.",
        ),
    ]
    for title, raw_text in fallback_specs:
        description = _summarize_detail_text(raw_text, limit=88)
        if description:
            steps.append({"title": title, "description": description})
        if len(steps) >= 3:
            break
    return steps


def _build_product_demo_block(product, manual, steps):
    if manual is not None:
        for section in manual.sections.all():
            title = _clean_detail_text(section.title) or "1분 데모"
            caption = _summarize_detail_text(section.content, limit=120) or _build_product_value_proposition(product)
            video_url = _clean_detail_text(section.video_url)
            if video_url:
                return {
                    "kind": "video",
                    "title": title,
                    "caption": caption,
                    "media_url": video_url,
                }
            image_url = _safe_media_url(getattr(section, "image", None))
            if image_url:
                return {
                    "kind": "image",
                    "title": title,
                    "caption": caption,
                    "media_url": image_url,
                }

    product_image_url = _safe_media_url(getattr(product, "image", None))
    if product_image_url:
        return {
            "kind": "image",
            "title": "대표 화면 미리보기",
            "caption": _build_product_value_proposition(product),
            "media_url": product_image_url,
        }

    return {
        "kind": "steps",
        "title": "1분 안에 보는 사용 흐름",
        "caption": _build_product_value_proposition(product),
        "media_url": "",
        "step_count": len(steps),
    }


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
            "description": "한 화면 대결과 AI 연습을 모두 지원하는 대표 전략 게임입니다.",
            "href": reverse("chess:play"),
        },
        {
            "emoji": "🧠",
            "title": "장기",
            "description": "한 화면 대결과 브라우저 AI 연습을 지원하는 전통 전략 게임입니다.",
            "href": reverse("janggi:play"),
        },
        {
            "emoji": "🦁",
            "title": "동물 장기",
            "description": "작은 판에서 사자를 지키며 한 화면 로컬 대결로 빠르게 즐깁니다.",
            "href": reverse("fairy_games:play_dobutsu"),
        },
        {
            "emoji": "🟡",
            "title": "커넥트 포",
            "description": "같은 화면에서 칩 4개를 먼저 연결하는 로컬 전략 게임입니다.",
            "href": reverse("fairy_games:play_cfour"),
        },
        {
            "emoji": "🧱",
            "title": "이솔레이션",
            "description": "이동 후 칸을 막아 상대를 가두는 한 화면 로컬 전략 게임입니다.",
            "href": reverse("fairy_games:play_isolation"),
        },
        {
            "emoji": "⚔",
            "title": "아택스",
            "description": "복제와 점프로 세력을 넓히는 한 화면 로컬 점령 게임입니다.",
            "href": reverse("fairy_games:play_ataxx"),
        },
        {
            "emoji": "🏁",
            "title": "브레이크스루",
            "description": "말 하나를 끝줄까지 먼저 돌파시키는 한 화면 로컬 게임입니다.",
            "href": reverse("fairy_games:play_breakthrough"),
        },
        {
            "emoji": "⚫",
            "title": "리버시",
            "description": "검은 돌과 흰 돌을 뒤집어 더 많은 칸을 차지하는 로컬 전략 게임입니다.",
            "href": reverse("fairy_games:play_reversi"),
        },
        {
            "emoji": "⚡",
            "title": "탭 순발력 챌린지",
            "description": "싱글 기록 도전과 1:1 대결로 반응속도를 겨루는 활동형 게임입니다.",
            "href": reverse("reflex_game:main"),
        },
        {
            "emoji": "🎲",
            "title": "교실 윷놀이",
            "description": "큰 화면에서 팀별로 윷을 던져 말판을 완주하는 협력 게임입니다.",
            "href": reverse("yut_game"),
        },
    ]


def _build_student_games_launch_url(request, token):
    path = reverse("dt_student_games_launch")
    query = urlencode({"token": token})
    return request.build_absolute_uri(f"{path}?{query}")


def _build_student_games_launch_path(token):
    path = reverse("dt_student_games_launch")
    query = urlencode({"token": token})
    return f"{path}?{query}"


def _build_qr_data_url(raw_text):
    if not raw_text:
        return ""

    qr_image = qrcode.make(raw_text)
    with io.BytesIO() as buffer:
        qr_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _student_games_storage_error_response(request, *, as_json):
    logger.exception("Student games ticket storage is unavailable.")
    if as_json:
        return JsonResponse(
            {
                "success": False,
                "error": STUDENT_GAMES_UNAVAILABLE_MESSAGE,
            },
            status=503,
        )
    return render(
        request,
        "products/dutyticker/student_games_invalid.html",
        {
            "hide_navbar": True,
            "student_games_invalid_message": STUDENT_GAMES_UNAVAILABLE_MESSAGE,
        },
        status=503,
    )


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
        _normalize_catalog_section_key,
    )

    products = filter_discoverable_products(
        Product.objects.filter(is_active=True).order_by('display_order', '-created_at')
    )
    product_list = _attach_product_launch_meta(list(products), user=request.user)
    surface_products = [product for product in product_list if bool(getattr(product, "is_active", False))]
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
            **build_product_list_page_seo(request).as_context(),
        },
    )

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    is_owned = False
    if request.user.is_authenticated:
        is_owned = request.user.owned_products.filter(product=product).exists() or product.price == 0
    from core.views import _attach_product_launch_meta, _resolve_product_launch_url

    product = _attach_product_launch_meta([product], user=request.user)[0]
    manual = (
        ServiceManual.objects.filter(product=product, is_published=True)
        .prefetch_related("sections")
        .first()
    )
    features = list(product.features.all())
    launch_href, launch_is_external = _resolve_product_launch_url(product, user=request.user)
    can_launch = bool(launch_href) and launch_href != request.path
    can_start = can_launch and (product.price == 0 or is_owned)
    access_label = getattr(product, "home_access_status_label", "") or "로그인 필요"

    start_href = launch_href if can_start else ""
    start_label = getattr(product, "product_start_label_override", "") or "바로 시작"
    start_is_external = can_start and launch_is_external
    if can_start and access_label == "로그인 필요" and not request.user.is_authenticated and not launch_is_external:
        start_href = f"{reverse('account_login')}?{urlencode({'next': launch_href})}"
        start_label = "로그인하고 시작"
        start_is_external = False
    elif can_start and launch_is_external and access_label in PUBLIC_PREVIEW_ACCESS_LABELS:
        start_label = "바로 체험하기"
    elif can_start and launch_is_external:
        start_label = "새 창에서 시작"
    elif can_start and access_label in PUBLIC_PREVIEW_ACCESS_LABELS:
        start_label = getattr(product, "product_start_label_override", "") or "바로 체험하기"

    guide_href = getattr(product, "guide_url", "") or SERVICE_GUIDE_PADLET_URL
    guide_label = "1분 가이드 보기" if getattr(product, "guide_url", "") else "가이드 찾기"
    quick_preview_steps = _build_product_detail_steps(product, manual, features)
    demo_block = _build_product_demo_block(product, manual, quick_preview_steps)

    seo_meta = build_product_detail_seo(request, product)
    response = render(
        request,
        'products/detail.html',
        {
            'product': product,
            'product_manual': manual,
            'product_features': features[:3],
            'product_value_proposition': _build_product_value_proposition(product),
            'product_audience': _build_product_audience_copy(product),
            'product_access_label': access_label,
            'product_access_copy': _build_product_access_copy(product),
            'product_demo_block': demo_block,
            'quick_preview_steps': quick_preview_steps,
            'is_owned': is_owned,
            'launch_href': launch_href,
            'launch_is_external': launch_is_external,
            'can_launch': can_launch,
            'can_start': can_start,
            'start_href': start_href,
            'start_label': start_label,
            'start_is_external': start_is_external,
            'guide_href': guide_href,
            'guide_label': guide_label,
            **seo_meta.as_context(),
        },
    )
    if seo_meta.robots.startswith("noindex"):
        response["X-Robots-Tag"] = seo_meta.robots.replace(",", ", ")
    return response

def product_preview(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    features = product.features.all()
    from core.views import _attach_product_launch_meta, _resolve_product_launch_url
    product = _attach_product_launch_meta([product], user=request.user)[0]
    launch_href, launch_is_external = _resolve_product_launch_url(product, user=request.user)
    return render(request, 'products/partials/preview_modal.html', {
        'product': product,
        'features': features,
        'launch_href': launch_href,
        'launch_is_external': launch_is_external,
    })


def tts_announce_view(request):
    seo = build_route_page_seo(
        request,
        title="교실 방송 TTS - Eduitit",
        description=PRODUCT_DETAIL_AUDIENCE_BY_ROUTE["tts_announce"],
        route_name="tts_announce",
    )
    classroom = get_active_classroom_for_request(request) if request.user.is_authenticated else None
    today = timezone.localdate()
    today_js_day = (today.weekday() + 1) % 7

    schedule_rows = []
    schedule_source_label = "샘플 시간표 프리셋"
    schedule_source_note = "교시 안내가 필요할 때 아래에서 바로 가져와 읽을 수 있습니다."

    if request.user.is_authenticated:
        schedule_queryset = apply_classroom_scope(
            DTSchedule.objects.filter(user=request.user, day=today_js_day),
            classroom,
        ).order_by("period", "id")
        if schedule_queryset.exists():
            schedule_rows = build_tts_announcement_rows(schedule_queryset, date=today)
            schedule_source_label = "오늘 시간표 프리셋"
            schedule_source_note = "알림판을 열지 않아도 교시 안내 문구만 빠르게 가져와 읽을 수 있습니다."

    if not schedule_rows:
        schedule_rows = build_demo_tts_rows(date=today)

    schedule_rows = annotate_tts_rows(schedule_rows)
    next_row = next((row for row in schedule_rows if row.get("is_next")), schedule_rows[0] if schedule_rows else None)
    active_classroom_name = getattr(classroom, "name", "") or "데모 학급"
    broadcast_groups = build_tts_broadcast_template_groups(active_classroom_name)
    first_template = next(
        (item for group in broadcast_groups for item in group.get("items", [])),
        None,
    )
    broadcast_template_count = sum(len(group.get("items", [])) for group in broadcast_groups)
    initial_message_text = ""
    initial_message_title = "방송 문구"
    initial_message_source = "빠른 문구"

    if first_template is not None:
        initial_message_text = first_template["message"]
        initial_message_title = first_template["title"]
        initial_message_source = broadcast_groups[0]["title"] if broadcast_groups else "빠른 문구"
    elif next_row is not None:
        initial_message_text = next_row["announcement_text"]
        initial_message_title = f'{next_row["period_label"]} · {next_row["subject"]}'
        initial_message_source = schedule_source_label

    return render(
        request,
        "products/tts_announce.html",
        {
            **seo.as_context(),
            "hide_navbar": True,
            "broadcast_groups": broadcast_groups,
            "broadcast_template_count": broadcast_template_count,
            "schedule_rows": schedule_rows,
            "schedule_source_label": schedule_source_label,
            "schedule_source_note": schedule_source_note,
            "active_classroom_name": active_classroom_name,
            "next_schedule_subject": next_row["subject"] if next_row else "",
            "next_schedule_countdown": next_row["countdown_label"] if next_row else "바로 쓸 시간표 문구가 없습니다.",
            "next_schedule_time_label": next_row["announce_time_label"] if next_row else "",
            "initial_message_text": initial_message_text,
            "initial_message_title": initial_message_title,
            "initial_message_source": initial_message_source,
        },
    )


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

    try:
        _, raw_token = _issue_student_games_launch_ticket(request)
    except (OperationalError, ProgrammingError):
        return _student_games_storage_error_response(request, as_json=True)
    launch_url = _build_student_games_launch_url(request, raw_token)
    return JsonResponse(
        {
            "success": True,
            "launch_url": launch_url,
            "launch_path": _build_student_games_launch_path(raw_token),
            "qr_data_url": _build_qr_data_url(launch_url),
            "expires_in_minutes": _student_games_launch_ticket_ttl_minutes(),
        }
    )


def dutyticker_student_games_launch(request):
    token = (request.GET.get("token") or "").strip()
    try:
        ticket = _find_valid_student_games_launch_ticket(token)
    except (OperationalError, ProgrammingError):
        return _student_games_storage_error_response(request, as_json=False)
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
        "classroom_id": str(ticket.classroom_id) if ticket.classroom_id else None,
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
