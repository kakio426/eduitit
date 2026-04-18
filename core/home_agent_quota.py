from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from .models import HomeAgentQuotaBoost, HomeAgentQuotaState, HomeAgentUsageLog


DEFAULT_HOME_AGENT_DAILY_LIMIT = 15
BOOSTED_HOME_AGENT_DAILY_LIMIT = 30
BOOST_DURATION_DAYS = 14
LIMIT_REACHED_ERROR_CODE = "home_agent_quota_exceeded"
LIMIT_REQUEST_LABEL = "한도 요청"
LIMIT_MODAL_TITLE = "오늘 AI 한도 끝"
LIMIT_MODAL_MESSAGE = (
    "인디스쿨 함께 사용하기에 홍보글을 올린 뒤 캡처를 개발자 채팅으로 보내주시면, "
    "감사의 의미로 2주 동안 하루 30회까지 추가로 이용하실 수 있도록 열어드릴게요."
)
LIMIT_PREFILL_TEXT = (
    "AI 교무비서 한도를 모두 사용했어요. 인디스쿨 함께 사용하기에 올린 홍보글 캡처를 보내드립니다. "
    "확인해 주시면 감사의 의미로 제공되는 2주 추가 이용 한도를 부탁드려요."
)


def _now():
    return timezone.now()


def _today():
    return timezone.localdate()


def _local_label(value):
    if not value:
        return ""
    return date_format(timezone.localtime(value), "n월 j일 H:i")


def get_or_create_home_agent_quota_state(user):
    state, _ = HomeAgentQuotaState.objects.get_or_create(user=user)
    return state


def get_active_home_agent_quota_boost(user, *, at=None):
    if not getattr(user, "is_authenticated", False):
        return None
    moment = at or _now()
    return (
        HomeAgentQuotaBoost.objects.filter(
            user=user,
            starts_at__lte=moment,
            ends_at__gt=moment,
        )
        .order_by("-ends_at", "-id")
        .first()
    )


def get_home_agent_daily_limit(user, *, at=None):
    active_boost = get_active_home_agent_quota_boost(user, at=at)
    if active_boost:
        return int(active_boost.daily_limit or BOOSTED_HOME_AGENT_DAILY_LIMIT)
    return DEFAULT_HOME_AGENT_DAILY_LIMIT


def get_home_agent_used_count(user, *, on_date=None):
    if not getattr(user, "is_authenticated", False):
        return 0
    target_date = on_date or _today()
    return HomeAgentUsageLog.objects.filter(user=user, usage_date=target_date).count()


def get_home_agent_remaining_count(user, *, on_date=None):
    limit = get_home_agent_daily_limit(user)
    used = get_home_agent_used_count(user, on_date=on_date)
    return max(limit - used, 0)


def build_home_agent_limit_request_url():
    query = urlencode(
        {
            "prefill": LIMIT_PREFILL_TEXT,
            "source": "home_agent_limit",
        }
    )
    return f"{reverse('messagebox:developer_chat')}?{query}"


def build_home_agent_quota_snapshot(user):
    active_boost = get_active_home_agent_quota_boost(user)
    used_count = get_home_agent_used_count(user)
    daily_limit = get_home_agent_daily_limit(user)
    remaining_count = max(daily_limit - used_count, 0)
    return {
        "daily_limit": daily_limit,
        "used_count": used_count,
        "remaining_count": remaining_count,
        "has_active_boost": bool(active_boost),
        "status_label": f"증액 {daily_limit}회" if active_boost else f"기본 {DEFAULT_HOME_AGENT_DAILY_LIMIT}회",
        "active_until_label": _local_label(active_boost.ends_at if active_boost else None),
        "grant_button_label": "2주 연장" if active_boost else f"2주간 {BOOSTED_HOME_AGENT_DAILY_LIMIT}회",
        "request_url": build_home_agent_limit_request_url(),
    }


def is_home_agent_limit_reached(user):
    if not getattr(user, "is_authenticated", False):
        return False
    return get_home_agent_used_count(user) >= get_home_agent_daily_limit(user)


def record_home_agent_usage(user, *, mode_key="", provider=""):
    if not getattr(user, "is_authenticated", False):
        return None
    return HomeAgentUsageLog.objects.create(
        user=user,
        usage_date=_today(),
        mode_key=str(mode_key or "").strip(),
        provider=str(provider or "").strip(),
    )


def mark_home_agent_limit_reached(user):
    if not getattr(user, "is_authenticated", False):
        return None
    state = get_or_create_home_agent_quota_state(user)
    state.last_limit_reached_at = _now()
    state.prompt_dismissed_at = None
    state.save(update_fields=["last_limit_reached_at", "prompt_dismissed_at", "updated_at"])
    return state


def dismiss_home_agent_limit_prompt(user):
    if not getattr(user, "is_authenticated", False):
        return None
    state = get_or_create_home_agent_quota_state(user)
    state.prompt_dismissed_at = _now()
    state.save(update_fields=["prompt_dismissed_at", "updated_at"])
    return state


def has_home_agent_limit_nav_chip(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if get_active_home_agent_quota_boost(user):
        return False
    state = HomeAgentQuotaState.objects.filter(user=user).first()
    if not state or not state.last_limit_reached_at or not state.prompt_dismissed_at:
        return False
    if state.prompt_dismissed_at < state.last_limit_reached_at:
        return False
    return timezone.localtime(state.last_limit_reached_at).date() == _today()


def build_home_agent_limit_nav_action(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return {
        "visible": has_home_agent_limit_nav_chip(user),
        "label": LIMIT_REQUEST_LABEL,
        "href": build_home_agent_limit_request_url(),
    }


def build_home_agent_limit_response_payload(user):
    snapshot = build_home_agent_quota_snapshot(user)
    return {
        "error": "오늘 AI 한도를 모두 썼어요.",
        "error_code": LIMIT_REACHED_ERROR_CODE,
        "quota": {
            "title": LIMIT_MODAL_TITLE,
            "message": LIMIT_MODAL_MESSAGE,
            "status_text": f"오늘 {snapshot['used_count']} / {snapshot['daily_limit']}회 사용",
            "action_label": "개발자 채팅",
            "action_href": snapshot["request_url"],
            "dismiss_url": reverse("home_agent_quota_dismiss"),
            "chip_label": LIMIT_REQUEST_LABEL,
        },
    }


def grant_home_agent_quota_boost(
    user,
    *,
    granted_by=None,
    source_thread_id=None,
    daily_limit=BOOSTED_HOME_AGENT_DAILY_LIMIT,
    duration_days=BOOST_DURATION_DAYS,
    note="",
):
    moment = _now()
    latest_active_or_future = (
        HomeAgentQuotaBoost.objects.filter(user=user, ends_at__gt=moment)
        .order_by("-ends_at", "-id")
        .first()
    )
    starts_at = latest_active_or_future.ends_at if latest_active_or_future else moment
    boost = HomeAgentQuotaBoost.objects.create(
        user=user,
        daily_limit=daily_limit,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(days=duration_days),
        granted_by=granted_by,
        source_thread_id=source_thread_id,
        note=str(note or "").strip(),
    )
    state = get_or_create_home_agent_quota_state(user)
    state.last_limit_reached_at = None
    state.prompt_dismissed_at = None
    state.save(update_fields=["last_limit_reached_at", "prompt_dismissed_at", "updated_at"])
    return boost
