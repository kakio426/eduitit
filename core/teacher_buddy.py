from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from difflib import SequenceMatcher
from html import escape
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import (
    TeacherBuddyDailyProgress,
    TeacherBuddySkinUnlock,
    TeacherBuddySocialRewardLog,
    TeacherBuddyState,
    TeacherBuddyUnlock,
    UserProfile,
)
from .seo import SITE_CANONICAL_BASE_URL
from .service_launcher import resolve_home_section_key
from .teacher_buddy_catalog import (
    COMMON_BUDDY_KEYS,
    LOCKED_BUDDY_ASCII,
    RARITY_COMMON,
    RARITY_EPIC,
    RARITY_LEGENDARY,
    RARITY_RARE,
    TOTAL_BUDDY_COUNT,
    TOTAL_SKIN_COUNT,
    TeacherBuddyDefinition,
    TeacherBuddySkinDefinition,
    all_teacher_buddies,
    get_teacher_buddy,
    get_teacher_buddy_skin,
    get_teacher_buddy_palette,
    get_teacher_buddy_skins_for_buddy,
    with_particle,
)


HOME_BUDDY_TRACKABLE_SOURCES = {
    "home_quick",
    "home_section",
    "home_game",
    "home_grid",
    "home_mini",
}
ELIGIBLE_ROLES = {"school", "instructor"}
HOME_DAILY_SECTION_TARGET = 3
MAX_DRAW_TOKEN_COUNT = 5
LEGENDARY_UNLOCK_DAYS = 60
SNS_REWARD_MIN_TEXT = 40
SNS_REWARD_MIN_TEXT_WITH_IMAGE = 20
SNS_SIMILARITY_WINDOW = 14
SNS_DUPLICATE_LOOKBACK_DAYS = 30
SNS_SIMILARITY_THRESHOLD = 0.82
RARITY_WEIGHTS_BEFORE_LEGENDARY = {
    RARITY_COMMON: 58,
    RARITY_RARE: 30,
    RARITY_EPIC: 12,
    RARITY_LEGENDARY: 0,
}
RARITY_WEIGHTS_AFTER_LEGENDARY = {
    RARITY_COMMON: 53,
    RARITY_RARE: 28,
    RARITY_EPIC: 14,
    RARITY_LEGENDARY: 5,
}
# After rarity is chosen, new bodies stay most likely, locked styles are next,
# and repeats remain possible but intentionally least likely.
DRAW_CANDIDATE_WEIGHTS_BY_RARITY = {
    RARITY_COMMON: {
        "new_buddy": 4,
        "new_style": 2,
        "repeat_buddy": 1,
    },
    RARITY_RARE: {
        "new_buddy": 4,
        "new_style": 2,
        "repeat_buddy": 1,
    },
    RARITY_EPIC: {
        "new_buddy": 5,
        "new_style": 0,
        "repeat_buddy": 1,
    },
    RARITY_LEGENDARY: {
        "new_buddy": 1,
        "new_style": 0,
        "repeat_buddy": 0,
    },
}
COSMETIC_TIERS = (
    (0, "starter", "새싹 링"),
    (12, "glow", "반짝 링"),
    (36, "aurora", "오로라 프레임"),
    (72, "studio", "스튜디오 프레임"),
)
DEFAULT_STYLE_KEY = ""
DRAW_REVEAL_THEME_BY_RARITY = {
    RARITY_COMMON: "common",
    RARITY_RARE: "rare",
    RARITY_EPIC: "epic",
    RARITY_LEGENDARY: "legendary",
}


class TeacherBuddyError(Exception):
    pass


def teacher_buddy_enabled() -> bool:
    return bool(getattr(settings, "HOME_TEACHER_BUDDY_ENABLED", False))


def teacher_buddy_user_is_eligible(user) -> bool:
    if not teacher_buddy_enabled():
        return False
    if not getattr(user, "is_authenticated", False):
        return False
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile.role in ELIGIBLE_ROLES


def _today() -> date:
    return timezone.localdate()


def _sns_bonus_key(value: date | None = None) -> str:
    target = value or _today()
    return target.isoformat()


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _content_hash(value: str) -> str:
    normalized = _normalize_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def _similarity_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _starter_buddy_key_for_user(user) -> str:
    if not COMMON_BUDDY_KEYS:
        raise TeacherBuddyError("Starter buddies are not configured.")
    seed_value = f"starter:{user.pk}:{user.username}"
    return random.Random(seed_value).choice(list(COMMON_BUDDY_KEYS))


def _collection_completed(unlock_count: int) -> bool:
    return unlock_count >= TOTAL_BUDDY_COUNT


def _legendary_pool_unlocked(state: TeacherBuddyState) -> bool:
    return int(state.qualifying_day_count or 0) >= LEGENDARY_UNLOCK_DAYS


def _remaining_legendary_days(state: TeacherBuddyState) -> int:
    return max(0, LEGENDARY_UNLOCK_DAYS - int(state.qualifying_day_count or 0))


def _safe_nickname_for_user(user) -> str:
    profile = UserProfile.objects.filter(user=user).first()
    if profile and profile.nickname:
        return profile.nickname
    return getattr(user, "username", "") or "사용자"


def _cosmetic_tier(sticker_dust: int) -> tuple[str, str]:
    chosen_key = COSMETIC_TIERS[0][1]
    chosen_label = COSMETIC_TIERS[0][2]
    for minimum, tier_key, tier_label in COSMETIC_TIERS:
        if sticker_dust >= minimum:
            chosen_key = tier_key
            chosen_label = tier_label
    return chosen_key, chosen_label


def _build_palette_payload(palette_key: str, *, accent_override: str = "") -> dict[str, str]:
    tokens = dict(get_teacher_buddy_palette(palette_key))
    if accent_override:
        tokens["accent"] = accent_override
    tokens["gradient"] = f"linear-gradient(135deg, {tokens['bg_start']}, {tokens['bg_end']})"
    return tokens


def _serialize_skin(
    *,
    skin: TeacherBuddySkinDefinition | None,
    buddy: TeacherBuddyDefinition,
    unlocked: bool,
    active_key: str,
    active_skin_key: str,
    profile_key: str,
    profile_skin_key: str,
) -> dict[str, object]:
    palette_key = skin.palette if skin else buddy.palette
    palette_tokens = _build_palette_payload(palette_key, accent_override=skin.avatar_accent if skin else "")
    resolved_skin_key = skin.key if skin else DEFAULT_STYLE_KEY
    return {
        "key": resolved_skin_key,
        "skin_key": resolved_skin_key,
        "buddy_key": buddy.key,
        "label": skin.label if skin else "기본 스타일",
        "palette": palette_key,
        "palette_tokens": palette_tokens,
        "preview_badge": skin.preview_badge if skin else buddy.avatar_mark,
        "avatar_accent": skin.avatar_accent if skin else palette_tokens.get("accent", ""),
        "unlock_cost_dust": int(skin.unlock_cost_dust if skin else 0),
        "is_default": skin is None,
        "is_unlocked": unlocked,
        "is_active_style": buddy.key == active_key and (active_skin_key or DEFAULT_STYLE_KEY) == resolved_skin_key,
        "is_profile_style": buddy.key == profile_key and (profile_skin_key or DEFAULT_STYLE_KEY) == resolved_skin_key,
    }


def _serialize_unlocked_skin_result(
    *,
    skin: TeacherBuddySkinDefinition,
    buddy: TeacherBuddyDefinition,
) -> dict[str, object]:
    palette_tokens = _build_palette_payload(skin.palette, accent_override=skin.avatar_accent)
    return {
        "key": skin.key,
        "skin_key": skin.key,
        "buddy_key": buddy.key,
        "buddy_name": buddy.name,
        "label": skin.label,
        "palette": skin.palette,
        "palette_tokens": palette_tokens,
        "preview_badge": skin.preview_badge,
        "avatar_accent": skin.avatar_accent,
        "idle_ascii": buddy.idle_ascii,
        "unlock_ascii": buddy.unlock_ascii,
        "rarity": buddy.rarity,
        "rarity_label": buddy.rarity_label,
        "selected_skin_label": skin.label,
    }


def _style_summary_text(*, buddy_unlocked: bool, unlocked_skin_count: int, total_skin_count: int) -> str:
    total_styles = 1 + total_skin_count
    unlocked_styles = (1 + unlocked_skin_count) if buddy_unlocked else 0
    return f"스타일 {unlocked_styles}/{total_styles}"


def _resolve_style_skin_key(state_value: str, buddy_key: str, selected_buddy_key: str) -> str:
    if buddy_key != selected_buddy_key:
        return ""
    return str(state_value or "")


def _build_style_options(
    *,
    user,
    buddy: TeacherBuddyDefinition,
    buddy_unlocked: bool,
    active_key: str,
    active_skin_key: str,
    profile_key: str,
    profile_skin_key: str,
) -> list[dict[str, object]]:
    unlocked_skin_keys = set(
        TeacherBuddySkinUnlock.objects.filter(user=user, buddy_key=buddy.key).values_list("skin_key", flat=True)
    )
    options = [
        _serialize_skin(
            skin=None,
            buddy=buddy,
            unlocked=buddy_unlocked,
            active_key=active_key,
            active_skin_key=active_skin_key,
            profile_key=profile_key,
            profile_skin_key=profile_skin_key,
        )
    ]
    for skin in get_teacher_buddy_skins_for_buddy(buddy.key):
        options.append(
            _serialize_skin(
                skin=skin,
                buddy=buddy,
                unlocked=skin.key in unlocked_skin_keys,
                active_key=active_key,
                active_skin_key=active_skin_key,
                profile_key=profile_key,
                profile_skin_key=profile_skin_key,
            )
        )
    return options


def _locked_buddy_payload(
    buddy: TeacherBuddyDefinition,
    *,
    active_key: str = "",
    profile_key: str = "",
    active_skin_key: str = "",
    profile_skin_key: str = "",
) -> dict[str, object]:
    palette_tokens = {
        "bg_start": "#e2e8f0",
        "bg_end": "#cbd5e1",
        "text": "#475569",
        "accent": "#94a3b8",
        "ring": "#e2e8f0",
        "gradient": "linear-gradient(135deg, #e2e8f0, #cbd5e1)",
    }
    return {
        "key": buddy.key,
        "name": buddy.name,
        "rarity": buddy.rarity,
        "rarity_label": buddy.rarity_label,
        "palette": buddy.palette,
        "palette_tokens": palette_tokens,
        "avatar_mark": "?",
        "selected_skin_key": "",
        "selected_skin_label": "",
        "share_frame": buddy.share_frame,
        "silhouette_family": buddy.silhouette_family,
        "share_caption": buddy.share_caption,
        "share_gradient_start": buddy.share_gradient[0],
        "share_gradient_end": buddy.share_gradient[1],
        "idle_ascii": LOCKED_BUDDY_ASCII,
        "unlock_ascii": "",
        "messages": (),
        "is_locked": True,
        "is_unlocked": False,
        "is_active": buddy.key == active_key,
        "is_profile": buddy.key == profile_key,
        "obtained_at": None,
        "obtained_via": "",
        "style_options": _build_style_options(
            user=None,
            buddy=buddy,
            buddy_unlocked=False,
            active_key=active_key,
            active_skin_key=active_skin_key,
            profile_key=profile_key,
            profile_skin_key=profile_skin_key,
        ) if False else [],
        "style_total_count": 1 + len(get_teacher_buddy_skins_for_buddy(buddy.key)),
        "style_unlocked_count": 0,
        "style_summary_text": _style_summary_text(
            buddy_unlocked=False,
            unlocked_skin_count=0,
            total_skin_count=len(get_teacher_buddy_skins_for_buddy(buddy.key)),
        ),
    }


def _serialize_buddy(
    buddy: TeacherBuddyDefinition,
    *,
    user=None,
    unlock: TeacherBuddyUnlock | None = None,
    active_key: str = "",
    profile_key: str = "",
    active_skin_key: str = "",
    profile_skin_key: str = "",
    selected_skin_key: str = "",
) -> dict[str, object]:
    if unlock is None:
        return _locked_buddy_payload(
            buddy,
            active_key=active_key,
            profile_key=profile_key,
            active_skin_key=active_skin_key,
            profile_skin_key=profile_skin_key,
        )
    selected_skin = None
    if selected_skin_key:
        try:
            selected_skin = get_teacher_buddy_skin(selected_skin_key)
        except KeyError:
            selected_skin = None
        if selected_skin and selected_skin.buddy_key != buddy.key:
            selected_skin = None
    palette_key = selected_skin.palette if selected_skin else buddy.palette
    style_unlock_map = {
        skin_unlock.skin_key: skin_unlock
        for skin_unlock in TeacherBuddySkinUnlock.objects.filter(user=user, buddy_key=buddy.key)
    } if user is not None else {}
    style_options = _build_style_options(
        user=user,
        buddy=buddy,
        buddy_unlocked=True,
        active_key=active_key,
        active_skin_key=active_skin_key,
        profile_key=profile_key,
        profile_skin_key=profile_skin_key,
    ) if user is not None else []
    unlocked_skin_count = len(style_unlock_map)
    return {
        "key": buddy.key,
        "name": buddy.name,
        "rarity": buddy.rarity,
        "rarity_label": buddy.rarity_label,
        "palette": palette_key,
        "palette_tokens": _build_palette_payload(palette_key, accent_override=selected_skin.avatar_accent if selected_skin else ""),
        "avatar_mark": buddy.avatar_mark,
        "selected_skin_key": selected_skin.key if selected_skin else "",
        "selected_skin_label": selected_skin.label if selected_skin else "기본 스타일",
        "share_frame": buddy.share_frame,
        "silhouette_family": buddy.silhouette_family,
        "share_caption": buddy.share_caption,
        "share_gradient_start": (selected_skin.share_gradient[0] if selected_skin else buddy.share_gradient[0]),
        "share_gradient_end": (selected_skin.share_gradient[1] if selected_skin else buddy.share_gradient[1]),
        "idle_ascii": buddy.idle_ascii,
        "unlock_ascii": buddy.unlock_ascii,
        "messages": buddy.messages,
        "is_locked": False,
        "is_unlocked": True,
        "is_active": buddy.key == active_key,
        "is_profile": buddy.key == profile_key,
        "obtained_at": unlock.obtained_at.isoformat() if unlock.obtained_at else None,
        "obtained_via": unlock.obtained_via,
        "style_options": style_options,
        "style_total_count": 1 + len(get_teacher_buddy_skins_for_buddy(buddy.key)),
        "style_unlocked_count": 1 + unlocked_skin_count,
        "style_summary_text": _style_summary_text(
            buddy_unlocked=True,
            unlocked_skin_count=unlocked_skin_count,
            total_skin_count=len(get_teacher_buddy_skins_for_buddy(buddy.key)),
        ),
    }


def _build_avatar_context_from_buddy_payload(
    buddy_payload: dict[str, object],
    *,
    initial: str,
    sticker_dust: int = 0,
) -> dict[str, object]:
    cosmetic_key, cosmetic_label = _cosmetic_tier(sticker_dust)
    return {
        "is_buddy": True,
        "initial": initial,
        "name": buddy_payload["name"],
        "rarity": buddy_payload["rarity"],
        "rarity_label": buddy_payload["rarity_label"],
        "avatar_mark": buddy_payload["avatar_mark"],
        "palette": buddy_payload["palette"],
        "palette_tokens": buddy_payload["palette_tokens"],
        "title": f"{buddy_payload['name']} 대표 메이트",
        "share_frame": buddy_payload.get("share_frame", ""),
        "cosmetic_tier": cosmetic_key,
        "cosmetic_tier_label": cosmetic_label,
    }


def _fallback_avatar_context(*, initial: str, label: str) -> dict[str, object]:
    return {
        "is_buddy": False,
        "initial": initial,
        "name": label,
        "rarity": "",
        "rarity_label": "",
        "avatar_mark": "",
        "palette": "fallback",
        "palette_tokens": {},
        "title": f"{label} 프로필",
        "share_frame": "",
        "cosmetic_tier": "starter",
        "cosmetic_tier_label": "새싹 링",
    }


def _pick_reaction_text(
    buddy_payload: dict[str, object],
    *,
    mood: str,
    user_id: int,
    activity_date: date,
) -> str:
    messages = tuple(buddy_payload.get("messages") or ())
    if not messages:
        return "오늘 흐름을 함께 살펴볼게요."
    if mood == "idle":
        return messages[0]
    if mood == "busy":
        return messages[min(1, len(messages) - 1)]
    return messages[min(2, len(messages) - 1)]


def _get_progress_for_date(user, activity_date: date) -> TeacherBuddyDailyProgress | None:
    return TeacherBuddyDailyProgress.objects.filter(user=user, activity_date=activity_date).first()


def _get_or_create_state_for_update(user) -> TeacherBuddyState:
    state, _ = TeacherBuddyState.objects.select_for_update().get_or_create(user=user)
    return state


def _sync_collection_completion(*, state: TeacherBuddyState, user) -> None:
    if state.collection_completed_at is not None:
        return
    unlock_count = TeacherBuddyUnlock.objects.filter(user=user).count()
    if _collection_completed(unlock_count):
        state.collection_completed_at = timezone.now()
        state.save(update_fields=["collection_completed_at"])


def _ensure_starter_unlocked(*, user, state: TeacherBuddyState) -> TeacherBuddyState:
    starter_key = _starter_buddy_key_for_user(user)
    unlock = TeacherBuddyUnlock.objects.filter(user=user, buddy_key=starter_key).first()
    if unlock is None:
        unlock = TeacherBuddyUnlock.objects.create(
            user=user,
            buddy_key=starter_key,
            rarity=RARITY_COMMON,
            obtained_via="starter",
        )

    updated_fields: list[str] = []
    if not state.active_buddy_key:
        state.active_buddy_key = starter_key
        updated_fields.append("active_buddy_key")
    if not state.profile_buddy_key:
        state.profile_buddy_key = starter_key
        updated_fields.append("profile_buddy_key")
    if state.starter_granted_at is None:
        state.starter_granted_at = unlock.obtained_at or timezone.now()
        updated_fields.append("starter_granted_at")
    if updated_fields:
        state.save(update_fields=updated_fields)
    return state


def _mark_qualifying_day(*, state: TeacherBuddyState, progress: TeacherBuddyDailyProgress) -> bool:
    if progress.qualified_for_legendary_day:
        return False
    progress.qualified_for_legendary_day = True
    progress.save(update_fields=["qualified_for_legendary_day"])
    state.qualifying_day_count = int(state.qualifying_day_count or 0) + 1
    state.save(update_fields=["qualifying_day_count"])
    return True


def _build_home_ticket_status_text(points_today: int, home_ticket_awarded: bool, token_granted: bool) -> str:
    if home_ticket_awarded and token_granted:
        return "오늘 반짝 조각 완성"
    if home_ticket_awarded:
        return "오늘 반짝 조각 완성 · 토큰 보관함 가득"
    remaining = max(0, HOME_DAILY_SECTION_TARGET - points_today)
    if remaining == HOME_DAILY_SECTION_TARGET:
        return "오늘 아직 시작 전"
    return f"서로 다른 홈 도구 {remaining}개 더"


def _build_sns_status_text(*, available: bool) -> str:
    return "오늘 SNS 보너스 가능" if available else "오늘 SNS 보너스 완료"


def _build_legendary_status_text(state: TeacherBuddyState) -> str:
    if _legendary_pool_unlocked(state):
        return "전설 풀 해금 완료"
    return f"전설 풀까지 {int(state.qualifying_day_count or 0)}/{LEGENDARY_UNLOCK_DAYS}일"


def _build_progress_summary(
    *,
    user,
    state: TeacherBuddyState,
    active_buddy_payload: dict[str, object],
    progress: TeacherBuddyDailyProgress | None,
) -> dict[str, object]:
    progress = progress or TeacherBuddyDailyProgress(
        user=user,
        activity_date=_today(),
        point_total=0,
        awarded_section_keys=[],
        first_launch_awarded=False,
        draw_awarded=False,
        home_ticket_awarded=False,
        qualified_for_legendary_day=False,
        sns_reward_awarded=False,
    )
    points_today = min(HOME_DAILY_SECTION_TARGET, int(progress.point_total or 0))
    token_ready = int(state.draw_token_count or 0) > 0
    collection_completed = bool(state.collection_completed_at)
    sns_bonus_available = str(state.last_sns_bonus_week_key or "") != _sns_bonus_key(progress.activity_date)
    token_granted = bool(progress.draw_awarded)
    if token_ready:
        mood = "cheer"
    elif points_today or not sns_bonus_available:
        mood = "busy"
    elif collection_completed:
        mood = "complete"
    else:
        mood = "idle"
    sticker_dust = int(state.sticker_dust or 0)
    cosmetic_key, cosmetic_label = _cosmetic_tier(sticker_dust)
    return {
        "points_today": points_today,
        "daily_cap": HOME_DAILY_SECTION_TARGET,
        "draw_token_count": int(state.draw_token_count or 0),
        "max_draw_token_count": MAX_DRAW_TOKEN_COUNT,
        "token_ready": token_ready,
        "mood": mood,
        "reaction_text": _pick_reaction_text(
            active_buddy_payload,
            mood=mood,
            user_id=user.id,
            activity_date=progress.activity_date,
        ),
        "collection_completed": collection_completed,
        "qualifying_day_count": int(state.qualifying_day_count or 0),
        "legendary_locked": not _legendary_pool_unlocked(state),
        "legendary_unlock_days": LEGENDARY_UNLOCK_DAYS,
        "legendary_days_remaining": _remaining_legendary_days(state),
        "legendary_progress_text": _build_legendary_status_text(state),
        "sns_reward_awarded": bool(progress.sns_reward_awarded),
        "sns_bonus_available": sns_bonus_available,
        "sns_bonus_text": _build_sns_status_text(available=sns_bonus_available),
        "home_ticket_awarded": bool(progress.home_ticket_awarded),
        "home_ticket_condition_text": "반짝 조각 3개면 메이트 뽑기 1개",
        "home_progress_text": f"오늘 반짝 조각 {points_today}/{HOME_DAILY_SECTION_TARGET}",
        "home_ticket_status_text": _build_home_ticket_status_text(
            points_today,
            bool(progress.home_ticket_awarded),
            token_granted,
        ),
        "sticker_dust": sticker_dust,
        "cosmetic_tier": cosmetic_key,
        "cosmetic_tier_label": cosmetic_label,
    }


def ensure_teacher_buddy_state(user, *, touch_home: bool = False) -> TeacherBuddyState | None:
    if not teacher_buddy_user_is_eligible(user):
        return None
    with transaction.atomic():
        state = _get_or_create_state_for_update(user)
        state = _ensure_starter_unlocked(user=user, state=state)
        _sync_collection_completion(state=state, user=user)
        if touch_home:
            state.last_home_seen_at = timezone.now()
            state.save(update_fields=["last_home_seen_at"])
        return state


def _build_collection_items(*, user, state: TeacherBuddyState) -> list[dict[str, object]]:
    unlock_map = {
        unlock.buddy_key: unlock
        for unlock in TeacherBuddyUnlock.objects.filter(user=user).order_by("obtained_at", "id")
    }
    profile_key = state.profile_buddy_key or state.active_buddy_key
    ordered_items: list[tuple[int, int, dict[str, object]]] = []
    for index, buddy in enumerate(all_teacher_buddies()):
        payload = _serialize_buddy(
            buddy,
            user=user,
            unlock=unlock_map.get(buddy.key),
            active_key=state.active_buddy_key,
            profile_key=profile_key,
            active_skin_key=_resolve_style_skin_key(state.active_skin_key, buddy.key, state.active_buddy_key),
            profile_skin_key=_resolve_style_skin_key(state.profile_skin_key, buddy.key, profile_key),
        )
        sort_rank = 3
        if payload["is_profile"]:
            sort_rank = 0
        elif payload["is_active"]:
            sort_rank = 1
        elif not payload["is_locked"]:
            sort_rank = 2
        ordered_items.append((sort_rank, index, payload))
    ordered_items.sort(key=lambda item: (item[0], item[1]))
    return [payload for _, _, payload in ordered_items]


def _serialize_state_buddy(
    *,
    user,
    state: TeacherBuddyState,
    buddy_key: str,
    selected_skin_key: str = "",
) -> dict[str, object]:
    unlock = TeacherBuddyUnlock.objects.filter(user=user, buddy_key=buddy_key).first()
    return _serialize_buddy(
        get_teacher_buddy(buddy_key),
        user=user,
        unlock=unlock,
        active_key=state.active_buddy_key,
        profile_key=state.profile_buddy_key or state.active_buddy_key,
        active_skin_key=_resolve_style_skin_key(state.active_skin_key, buddy_key, state.active_buddy_key),
        profile_skin_key=_resolve_style_skin_key(
            state.profile_skin_key,
            buddy_key,
            state.profile_buddy_key or state.active_buddy_key,
        ),
        selected_skin_key=selected_skin_key,
    )


def _build_share_copy_text(*, nickname: str, buddy_payload: dict[str, object]) -> str:
    return (
        f"{nickname}님의 교실 메이트는 {buddy_payload['name']}입니다. "
        f"{buddy_payload['share_caption']} #교실메이트 #Eduitit"
    )


def _collection_summary_text(user) -> str:
    unlocked_count = TeacherBuddyUnlock.objects.filter(user=user).count()
    unlocked_skin_count = TeacherBuddySkinUnlock.objects.filter(user=user).count()
    return f"{unlocked_count}/{TOTAL_BUDDY_COUNT} 메이트 · {unlocked_skin_count}/{TOTAL_SKIN_COUNT} 스타일"


def build_teacher_buddy_panel_context(user) -> dict[str, object] | None:
    state = ensure_teacher_buddy_state(user, touch_home=True)
    if state is None:
        return None

    progress = _get_progress_for_date(user, _today())
    active_key = state.active_buddy_key or state.profile_buddy_key
    active_buddy = _serialize_state_buddy(
        user=user,
        state=state,
        buddy_key=active_key,
        selected_skin_key=_resolve_style_skin_key(state.active_skin_key, active_key, state.active_buddy_key),
    )
    progress_summary = _build_progress_summary(
        user=user,
        state=state,
        active_buddy_payload=active_buddy,
        progress=progress,
    )
    return {
        "enabled": True,
        "title": "교실 메이트",
        "eyebrow": "오늘 흐름 위젯",
        "subtitle": "홈 도구 3개와 오늘 SNS 글 1개로 메이트 토큰을 모아요.",
        "active_buddy": active_buddy,
        "progress": progress_summary,
        "can_draw": bool(progress_summary["token_ready"]),
        "draw_button_label": "메이트 뽑기",
        "collection_summary_text": _collection_summary_text(user),
        "legendary_progress_text": progress_summary["legendary_progress_text"],
        "settings_href": f"{reverse('settings')}#teacher-buddy-settings",
        "sticker_dust_text": f"스타일 조각 {int(state.sticker_dust or 0)}개",
    }


def build_teacher_buddy_settings_context(user) -> dict[str, object] | None:
    state = ensure_teacher_buddy_state(user)
    if state is None:
        return None

    active_key = state.active_buddy_key or state.profile_buddy_key
    profile_key = state.profile_buddy_key or state.active_buddy_key
    active_buddy = _serialize_state_buddy(
        user=user,
        state=state,
        buddy_key=active_key,
        selected_skin_key=_resolve_style_skin_key(state.active_skin_key, active_key, state.active_buddy_key),
    )
    profile_buddy = _serialize_state_buddy(
        user=user,
        state=state,
        buddy_key=profile_key,
        selected_skin_key=_resolve_style_skin_key(state.profile_skin_key, profile_key, profile_key),
    )
    progress_summary = _build_progress_summary(
        user=user,
        state=state,
        active_buddy_payload=active_buddy,
        progress=_get_progress_for_date(user, _today()),
    )
    nickname = _safe_nickname_for_user(user)
    share_copy_text = _build_share_copy_text(nickname=nickname, buddy_payload=profile_buddy)
    collection_items = _build_collection_items(user=user, state=state)
    sticker_dust = int(state.sticker_dust or 0)
    cosmetic_key, cosmetic_label = _cosmetic_tier(sticker_dust)
    share_path = reverse("teacher_buddy_share_page", kwargs={"public_share_token": state.public_share_token})
    share_image_path = reverse("teacher_buddy_share_image", kwargs={"public_share_token": state.public_share_token})
    return {
        "title": "내 메이트 프로필 허브",
        "subtitle": "SNS 대표 메이트와 홈 메이트를 한 곳에서 고르고 자랑해 보세요.",
        "active_buddy": active_buddy,
        "profile_buddy": profile_buddy,
        "collection_items": collection_items,
        "draw_token_count": int(state.draw_token_count or 0),
        "max_draw_token_count": MAX_DRAW_TOKEN_COUNT,
        "collection_completed": bool(state.collection_completed_at),
        "collection_summary_text": _collection_summary_text(user),
        "legendary_progress_text": progress_summary["legendary_progress_text"],
        "qualifying_day_count": int(state.qualifying_day_count or 0),
        "legendary_unlock_days": LEGENDARY_UNLOCK_DAYS,
        "share_copy_text": share_copy_text,
        "indischool_share_text": f"{share_copy_text}\n인디스쿨에도 오늘의 메이트 카드를 같이 올려 보세요.",
        "instagram_share_text": f"{share_copy_text}\n오늘의 메이트 카드도 함께 올려 보세요.",
        "community_share_url": f"{reverse('home')}?{urlencode({'compose': share_copy_text})}#home-community-section",
        "share_path": share_path,
        "share_url": f"{SITE_CANONICAL_BASE_URL}{share_path}",
        "share_image_path": share_image_path,
        "share_image_url": f"{SITE_CANONICAL_BASE_URL}{share_image_path}",
        "share_filename": f"eduitit-buddy-{profile_buddy['key']}.svg",
        "share_title": f"{nickname}님의 교실 메이트",
        "selection_mode_default": "profile",
        "sticker_dust": sticker_dust,
        "sticker_dust_text": f"스타일 조각 {sticker_dust}개",
        "buddy_collection_summary_text": f"{TeacherBuddyUnlock.objects.filter(user=user).count()}/{TOTAL_BUDDY_COUNT} 메이트",
        "style_collection_summary_text": f"{TeacherBuddySkinUnlock.objects.filter(user=user).count()}/{TOTAL_SKIN_COUNT} 스타일",
        "cosmetic_tier": cosmetic_key,
        "cosmetic_tier_label": cosmetic_label,
        "progress": progress_summary,
    }


def build_teacher_buddy_urls() -> dict[str, str]:
    return {
        "draw": reverse("teacher_buddy_draw"),
        "select": reverse("teacher_buddy_select"),
        "select_profile": reverse("teacher_buddy_select_profile"),
        "unlock_skin": reverse("teacher_buddy_unlock_skin"),
        "home": f"{reverse('home')}#teacher-buddy-panel",
        "settings": f"{reverse('settings')}#teacher-buddy-settings",
    }


def build_teacher_buddy_avatar_context(user) -> dict[str, object]:
    if not getattr(user, "is_authenticated", False):
        return _fallback_avatar_context(initial="?", label="사용자")

    initial = _safe_nickname_for_user(user)[:1] or "?"
    if not teacher_buddy_enabled():
        return _fallback_avatar_context(initial=initial, label=_safe_nickname_for_user(user))

    state = ensure_teacher_buddy_state(user)
    buddy_key = ""
    if state:
        buddy_key = state.profile_buddy_key or state.active_buddy_key
    if not buddy_key:
        return _fallback_avatar_context(initial=initial, label=_safe_nickname_for_user(user))

    unlock = TeacherBuddyUnlock.objects.filter(user=user, buddy_key=buddy_key).first()
    if unlock is None:
        return _fallback_avatar_context(initial=initial, label=_safe_nickname_for_user(user))

    buddy_payload = _serialize_state_buddy(
        user=user,
        state=state,
        buddy_key=buddy_key,
        selected_skin_key=_resolve_style_skin_key(state.profile_skin_key, buddy_key, buddy_key),
    )
    return _build_avatar_context_from_buddy_payload(
        buddy_payload,
        initial=initial,
        sticker_dust=int(getattr(state, "sticker_dust", 0) or 0),
    )


def attach_teacher_buddy_avatar_context(items) -> None:
    items = list(items or [])
    if not items:
        return

    user_map = {}
    for item in items:
        author = getattr(item, "author", None)
        if author is not None and getattr(author, "id", None):
            user_map[author.id] = author
    if not user_map:
        return

    user_ids = list(user_map.keys())
    profiles = {
        profile.user_id: profile
        for profile in UserProfile.objects.filter(user_id__in=user_ids)
    }
    states = {
        state.user_id: state
        for state in TeacherBuddyState.objects.filter(user_id__in=user_ids)
    }
    buddy_keys = []
    for state in states.values():
        buddy_key = state.profile_buddy_key or state.active_buddy_key
        if buddy_key:
            buddy_keys.append(buddy_key)
    unlocks = {
        (unlock.user_id, unlock.buddy_key): unlock
        for unlock in TeacherBuddyUnlock.objects.filter(user_id__in=user_ids, buddy_key__in=buddy_keys)
    }
    avatar_contexts = {}
    for user_id, user in user_map.items():
        profile = profiles.get(user_id)
        initial = (profile.nickname if profile and profile.nickname else user.username or "?")[:1]
        state = states.get(user_id)
        buddy_key = state.profile_buddy_key or state.active_buddy_key if state else ""
        unlock = unlocks.get((user_id, buddy_key))
        if state and buddy_key and unlock:
            buddy_payload = _serialize_state_buddy(
                user=user,
                state=state,
                buddy_key=buddy_key,
                selected_skin_key=_resolve_style_skin_key(state.profile_skin_key, buddy_key, buddy_key),
            )
            avatar_contexts[user_id] = _build_avatar_context_from_buddy_payload(
                buddy_payload,
                initial=initial or "?",
                sticker_dust=int(state.sticker_dust or 0),
            )
        else:
            label = profile.nickname if profile and profile.nickname else user.username
            avatar_contexts[user_id] = _fallback_avatar_context(initial=initial or "?", label=label or "사용자")

    for item in items:
        author = getattr(item, "author", None)
        context = avatar_contexts.get(getattr(author, "id", None))
        setattr(item, "teacher_buddy_avatar_context", context)


def record_teacher_buddy_progress(user, product, source: str) -> dict[str, object] | None:
    if not teacher_buddy_user_is_eligible(user):
        return None
    if source not in HOME_BUDDY_TRACKABLE_SOURCES:
        return None

    activity_date = _today()
    with transaction.atomic():
        state = _get_or_create_state_for_update(user)
        state = _ensure_starter_unlocked(user=user, state=state)
        progress, _ = TeacherBuddyDailyProgress.objects.select_for_update().get_or_create(
            user=user,
            activity_date=activity_date,
            defaults={
                "point_total": 0,
                "awarded_section_keys": [],
                "first_launch_awarded": False,
                "draw_awarded": False,
                "home_ticket_awarded": False,
                "qualified_for_legendary_day": False,
                "sns_reward_awarded": False,
            },
        )

        progress_updated_fields: list[str] = []
        state_updated_fields: list[str] = []
        section_key = resolve_home_section_key(product) or ""
        awarded_section_keys = list(progress.awarded_section_keys or [])

        if section_key and section_key not in awarded_section_keys and len(awarded_section_keys) < HOME_DAILY_SECTION_TARGET:
            awarded_section_keys.append(section_key)
            progress.awarded_section_keys = awarded_section_keys
            progress.point_total = len(awarded_section_keys)
            progress.first_launch_awarded = True
            progress_updated_fields.extend(["awarded_section_keys", "point_total", "first_launch_awarded"])
            state.total_points_earned = int(state.total_points_earned or 0) + 1
            state_updated_fields.append("total_points_earned")

        if progress.point_total >= HOME_DAILY_SECTION_TARGET and not progress.home_ticket_awarded:
            progress.home_ticket_awarded = True
            progress_updated_fields.append("home_ticket_awarded")
            _mark_qualifying_day(state=state, progress=progress)
            if int(state.draw_token_count or 0) < MAX_DRAW_TOKEN_COUNT:
                progress.draw_awarded = True
                progress_updated_fields.append("draw_awarded")
                state.draw_token_count = min(MAX_DRAW_TOKEN_COUNT, int(state.draw_token_count or 0) + 1)
                state_updated_fields.append("draw_token_count")

        if progress_updated_fields:
            progress.save(update_fields=list(dict.fromkeys(progress_updated_fields)))
        if state_updated_fields:
            state.save(update_fields=list(dict.fromkeys(state_updated_fields)))

        _sync_collection_completion(state=state, user=user)
        active_key = state.active_buddy_key or state.profile_buddy_key
        active_buddy_payload = _serialize_state_buddy(
            user=user,
            state=state,
            buddy_key=active_key,
            selected_skin_key=_resolve_style_skin_key(state.active_skin_key, active_key, state.active_buddy_key),
        )
        return _build_progress_summary(
            user=user,
            state=state,
            active_buddy_payload=active_buddy_payload,
            progress=progress,
        )


def _build_sns_reward_payload(
    *,
    user,
    state: TeacherBuddyState,
    progress: TeacherBuddyDailyProgress,
    active_buddy_payload: dict[str, object],
    message: str,
    reward_granted: bool,
) -> dict[str, object]:
    buddy_progress = _build_progress_summary(
        user=user,
        state=state,
        active_buddy_payload=active_buddy_payload,
        progress=progress,
    )
    return {
        "reward_granted": reward_granted,
        "draw_token_count": int(state.draw_token_count or 0),
        "qualifying_day_count": int(state.qualifying_day_count or 0),
        "legendary_locked": not _legendary_pool_unlocked(state),
        "message": message,
        "buddy_progress": buddy_progress,
    }


def record_teacher_buddy_sns_reward(user, post) -> dict[str, object] | None:
    if not teacher_buddy_user_is_eligible(user):
        return None
    if getattr(post, "post_type", "") != "general":
        return None

    content = str(getattr(post, "content", "") or "")
    normalized_text = _normalize_text(content)
    has_image = bool(getattr(post, "image", None))
    min_length = SNS_REWARD_MIN_TEXT_WITH_IMAGE if has_image else SNS_REWARD_MIN_TEXT
    content_hash = _content_hash(content)
    activity_date = _today()
    current_day_key = _sns_bonus_key(activity_date)

    with transaction.atomic():
        state = _get_or_create_state_for_update(user)
        state = _ensure_starter_unlocked(user=user, state=state)
        progress, _ = TeacherBuddyDailyProgress.objects.select_for_update().get_or_create(
            user=user,
            activity_date=activity_date,
            defaults={
                "point_total": 0,
                "awarded_section_keys": [],
                "first_launch_awarded": False,
                "draw_awarded": False,
                "home_ticket_awarded": False,
                "qualified_for_legendary_day": False,
                "sns_reward_awarded": False,
            },
        )
        active_key = state.active_buddy_key or state.profile_buddy_key
        active_buddy_payload = _serialize_state_buddy(
            user=user,
            state=state,
            buddy_key=active_key,
            selected_skin_key=_resolve_style_skin_key(state.active_skin_key, active_key, state.active_buddy_key),
        )

        def _log_and_payload(reward_granted: bool, reason: str, message: str) -> dict[str, object]:
            TeacherBuddySocialRewardLog.objects.create(
                user=user,
                post_id=getattr(post, "id", None),
                activity_date=activity_date,
                content_hash=content_hash,
                normalized_text=normalized_text,
                reward_granted=reward_granted,
                rejection_reason=reason,
            )
            return _build_sns_reward_payload(
                user=user,
                state=state,
                progress=progress,
                active_buddy_payload=active_buddy_payload,
                message=message,
                reward_granted=reward_granted,
            )

        if len(normalized_text) < min_length:
            return _log_and_payload(
                False,
                "too_short",
                f"오늘 SNS 보너스는 글 {min_length}자 이상일 때만 드려요.",
            )

        recent_cutoff = timezone.now() - timedelta(days=SNS_DUPLICATE_LOOKBACK_DAYS)
        if normalized_text and TeacherBuddySocialRewardLog.objects.filter(
            user=user,
            reward_granted=True,
            normalized_text=normalized_text,
            created_at__gte=recent_cutoff,
        ).exists():
            return _log_and_payload(
                False,
                "exact_repeat_30d",
                "같은 문장은 30일 동안 보너스를 다시 드리지 않아요.",
            )

        recent_reward_texts = list(
            TeacherBuddySocialRewardLog.objects.filter(user=user, reward_granted=True)
            .exclude(normalized_text="")
            .order_by("-created_at")
            .values_list("normalized_text", flat=True)[:SNS_SIMILARITY_WINDOW]
        )
        for recent_text in recent_reward_texts:
            if _similarity_ratio(normalized_text, recent_text) > SNS_SIMILARITY_THRESHOLD:
                return _log_and_payload(
                    False,
                    "similar_recent",
                    "최근 보상 글과 너무 비슷해서 오늘 보너스는 넘어갈게요.",
                )

        if str(state.last_sns_bonus_week_key or "") == current_day_key:
            return _log_and_payload(
                False,
                "already_rewarded_today",
                "오늘 SNS 보너스는 이미 받았어요.",
            )

        if int(state.draw_token_count or 0) >= MAX_DRAW_TOKEN_COUNT:
            return _log_and_payload(
                False,
                "token_cap_reached",
                f"토큰은 최대 {MAX_DRAW_TOKEN_COUNT}개까지 모을 수 있어요. 먼저 한 번 뽑아 보세요.",
            )

        progress.sns_reward_awarded = True
        progress.sns_reward_post_id = getattr(post, "id", None)
        progress.save(update_fields=["sns_reward_awarded", "sns_reward_post_id"])
        state.draw_token_count = min(MAX_DRAW_TOKEN_COUNT, int(state.draw_token_count or 0) + 1)
        state.last_sns_bonus_week_key = current_day_key
        state.save(update_fields=["draw_token_count", "last_sns_bonus_week_key"])

        TeacherBuddySocialRewardLog.objects.create(
            user=user,
            post_id=getattr(post, "id", None),
            activity_date=activity_date,
            content_hash=content_hash,
            normalized_text=normalized_text,
            reward_granted=True,
            rejection_reason="",
        )
        return _build_sns_reward_payload(
            user=user,
            state=state,
            progress=progress,
            active_buddy_payload=active_buddy_payload,
            message="오늘 SNS 보너스로 메이트 토큰이 1장 쌓였어요.",
            reward_granted=True,
        )


def _build_draw_groups(*, user, state: TeacherBuddyState) -> dict[str, list[tuple[TeacherBuddyDefinition, bool]]]:
    unique_groups, repeat_groups = _build_body_draw_groups(user=user, state=state)
    return {
        RARITY_COMMON: unique_groups[RARITY_COMMON] or repeat_groups[RARITY_COMMON],
        RARITY_RARE: unique_groups[RARITY_RARE] or repeat_groups[RARITY_RARE],
        RARITY_EPIC: unique_groups[RARITY_EPIC] or repeat_groups[RARITY_EPIC],
        RARITY_LEGENDARY: unique_groups[RARITY_LEGENDARY],
    }


def _build_body_draw_groups(*, user, state: TeacherBuddyState) -> tuple[
    dict[str, list[tuple[TeacherBuddyDefinition, bool]]],
    dict[str, list[tuple[TeacherBuddyDefinition, bool]]],
]:
    unlock_map = {
        unlock.buddy_key: unlock
        for unlock in TeacherBuddyUnlock.objects.filter(user=user)
    }
    unique_groups = {
        RARITY_COMMON: [],
        RARITY_RARE: [],
        RARITY_EPIC: [],
        RARITY_LEGENDARY: [],
    }
    repeat_groups = {
        RARITY_COMMON: [],
        RARITY_RARE: [],
        RARITY_EPIC: [],
    }
    legendary_open = _legendary_pool_unlocked(state)
    for buddy in all_teacher_buddies():
        unlock = unlock_map.get(buddy.key)
        if unlock is None:
            if buddy.rarity == RARITY_LEGENDARY and not legendary_open:
                continue
            unique_groups.setdefault(buddy.rarity, []).append((buddy, False))
            continue
        if buddy.rarity != RARITY_LEGENDARY:
            repeat_groups.setdefault(buddy.rarity, []).append((buddy, True))

    return unique_groups, repeat_groups


def _build_style_draw_groups(*, user) -> dict[str, list[TeacherBuddySkinDefinition]]:
    unlocked_buddy_keys = set(TeacherBuddyUnlock.objects.filter(user=user).values_list("buddy_key", flat=True))
    unlocked_skin_keys = set(TeacherBuddySkinUnlock.objects.filter(user=user).values_list("skin_key", flat=True))
    groups = {
        RARITY_COMMON: [],
        RARITY_RARE: [],
        RARITY_EPIC: [],
        RARITY_LEGENDARY: [],
    }
    for buddy_key in unlocked_buddy_keys:
        buddy = get_teacher_buddy(buddy_key)
        if buddy.rarity == RARITY_LEGENDARY:
            continue
        for skin in get_teacher_buddy_skins_for_buddy(buddy_key):
            if skin.key in unlocked_skin_keys:
                continue
            groups.setdefault(buddy.rarity, []).append(skin)
    return groups


def _choose_draw_candidate(*, user, state: TeacherBuddyState) -> tuple[str, object, bool] | None:
    unique_body_groups, repeat_body_groups = _build_body_draw_groups(user=user, state=state)
    style_groups = _build_style_draw_groups(user=user)
    weights = (
        RARITY_WEIGHTS_AFTER_LEGENDARY
        if _legendary_pool_unlocked(state)
        else RARITY_WEIGHTS_BEFORE_LEGENDARY
    )
    rarity_choices = [
        rarity
        for rarity in weights.keys()
        if int(weights.get(rarity, 0) or 0) > 0
        and (
            unique_body_groups.get(rarity)
            or style_groups.get(rarity)
            or repeat_body_groups.get(rarity)
        )
    ]
    if not rarity_choices:
        return None

    chosen_rarity = random.choices(
        rarity_choices,
        weights=[weights[rarity] for rarity in rarity_choices],
        k=1,
    )[0]
    candidate_weights = DRAW_CANDIDATE_WEIGHTS_BY_RARITY.get(chosen_rarity, {})
    weighted_candidates: list[tuple[str, object, bool]] = []

    for buddy, _ in unique_body_groups.get(chosen_rarity, []):
        weighted_candidates.extend(
            [("buddy", buddy, False)] * int(candidate_weights.get("new_buddy", 0) or 0)
        )
    for skin in style_groups.get(chosen_rarity, []):
        weighted_candidates.extend(
            [("style", skin, False)] * int(candidate_weights.get("new_style", 0) or 0)
        )
    for buddy, _ in repeat_body_groups.get(chosen_rarity, []):
        weighted_candidates.extend(
            [("buddy", buddy, True)] * int(candidate_weights.get("repeat_buddy", 0) or 0)
        )

    if not weighted_candidates:
        return None
    return random.choice(weighted_candidates)


def draw_teacher_buddy(user) -> dict[str, object]:
    if not teacher_buddy_user_is_eligible(user):
        raise TeacherBuddyError("교실 메이트는 교사 계정에서만 사용할 수 있어요.")

    with transaction.atomic():
        state = _get_or_create_state_for_update(user)
        state = _ensure_starter_unlocked(user=user, state=state)

        if int(state.draw_token_count or 0) <= 0:
            raise TeacherBuddyError("아직 뽑기권이 없어요. 홈과 SNS에서 꾸준히 활동해 보세요.")

        chosen = _choose_draw_candidate(user=user, state=state)
        if chosen is None:
            raise TeacherBuddyError("지금은 메이트 뽑기 풀이 비어 있어요.")

        draw_kind, draw_target, is_duplicate = chosen
        state.draw_token_count = max(0, int(state.draw_token_count or 0) - 1)
        update_fields = ["draw_token_count"]
        progress = _get_progress_for_date(user, _today())
        active_key = state.active_buddy_key or state.profile_buddy_key

        if draw_kind == "style":
            skin = draw_target
            buddy = get_teacher_buddy(skin.buddy_key)
            TeacherBuddySkinUnlock.objects.create(
                user=user,
                buddy_key=skin.buddy_key,
                skin_key=skin.key,
                obtained_via="draw",
            )
            state.save(update_fields=update_fields)
            active_payload = _serialize_state_buddy(
                user=user,
                state=state,
                buddy_key=active_key,
                selected_skin_key=_resolve_style_skin_key(state.active_skin_key, active_key, state.active_buddy_key),
            )
            collection_item = _serialize_state_buddy(
                user=user,
                state=state,
                buddy_key=buddy.key,
                selected_skin_key="",
            )
            unlocked_skin = _serialize_unlocked_skin_result(skin=skin, buddy=buddy)
            result_payload = _serialize_state_buddy(
                user=user,
                state=state,
                buddy_key=buddy.key,
                selected_skin_key=skin.key,
            )
            return {
                "status": "ok",
                "draw_result_kind": "style_unlock",
                "result_buddy": result_payload,
                "active_buddy": active_payload,
                "unlocked_buddy": collection_item,
                "unlocked_skin": unlocked_skin,
                "collection_item": collection_item,
                "draw_token_count": int(state.draw_token_count or 0),
                "collection_completed": bool(state.collection_completed_at),
                "collection_summary_text": _collection_summary_text(user),
                "sticker_dust": int(state.sticker_dust or 0),
                "dust_gained": 0,
                "message": f"{buddy.name}의 {skin.label} 스타일을 만났어요.",
                "result_rarity": buddy.rarity,
                "result_reveal_theme": DRAW_REVEAL_THEME_BY_RARITY.get(buddy.rarity, "common"),
                "result_title": f"{buddy.rarity_label} 스타일 등장",
                "result_is_duplicate": False,
                "buddy_progress": _build_progress_summary(
                    user=user,
                    state=state,
                    active_buddy_payload=active_payload,
                    progress=progress,
                ),
            }

        buddy = draw_target
        if is_duplicate:
            state.save(update_fields=update_fields)
            result_payload = _serialize_state_buddy(
                user=user,
                state=state,
                buddy_key=buddy.key,
                selected_skin_key="",
            )
            active_payload = _serialize_state_buddy(
                user=user,
                state=state,
                buddy_key=active_key,
                selected_skin_key=_resolve_style_skin_key(state.active_skin_key, active_key, state.active_buddy_key),
            )
            return {
                "status": "ok",
                "draw_result_kind": "duplicate",
                "result_buddy": result_payload,
                "active_buddy": active_payload,
                "unlocked_buddy": result_payload,
                "draw_token_count": int(state.draw_token_count or 0),
                "collection_completed": bool(state.collection_completed_at),
                "collection_summary_text": _collection_summary_text(user),
                "sticker_dust": int(state.sticker_dust or 0),
                "dust_gained": 0,
                "message": f"{with_particle(buddy.name, ('이', '가'))} 다시 찾아왔어요. 이번에는 같은 메이트예요.",
                "result_rarity": buddy.rarity,
                "result_reveal_theme": "duplicate",
                "result_title": "같은 메이트가 다시 나왔어요",
                "result_is_duplicate": True,
                "buddy_progress": _build_progress_summary(
                    user=user,
                    state=state,
                    active_buddy_payload=active_payload,
                    progress=progress,
                ),
            }

        unlock = TeacherBuddyUnlock.objects.create(
            user=user,
            buddy_key=buddy.key,
            rarity=buddy.rarity,
            obtained_via="draw",
        )
        state.active_buddy_key = buddy.key
        state.active_skin_key = ""
        update_fields.append("active_buddy_key")
        update_fields.append("active_skin_key")
        state.save(update_fields=update_fields)
        _sync_collection_completion(state=state, user=user)
        active_payload = _serialize_state_buddy(
            user=user,
            state=state,
            buddy_key=buddy.key,
            selected_skin_key="",
        )
        return {
            "status": "ok",
            "draw_result_kind": "unlock",
            "result_buddy": active_payload,
            "active_buddy": active_payload,
            "unlocked_buddy": active_payload,
            "draw_token_count": int(state.draw_token_count or 0),
            "collection_completed": bool(state.collection_completed_at),
            "collection_summary_text": _collection_summary_text(user),
            "sticker_dust": int(state.sticker_dust or 0),
            "dust_gained": 0,
            "message": f"{with_particle(buddy.name, ('이', '가'))} 새로 합류했어요.",
            "result_rarity": buddy.rarity,
            "result_reveal_theme": DRAW_REVEAL_THEME_BY_RARITY.get(buddy.rarity, "common"),
            "result_title": f"{buddy.rarity_label} 메이트 등장",
            "result_is_duplicate": False,
            "buddy_progress": _build_progress_summary(
                user=user,
                state=state,
                active_buddy_payload=active_payload,
                progress=progress,
            ),
        }


def _validated_skin_key_for_user(*, user, buddy_key: str, skin_key: str) -> str:
    normalized_skin_key = str(skin_key or "").strip()
    if not normalized_skin_key:
        return ""
    try:
        skin = get_teacher_buddy_skin(normalized_skin_key)
    except KeyError as exc:
        raise TeacherBuddyError("선택할 수 없는 스타일입니다.") from exc
    if skin.buddy_key != buddy_key:
        raise TeacherBuddyError("이 스타일은 선택한 메이트 전용입니다.")
    if not TeacherBuddySkinUnlock.objects.filter(user=user, skin_key=normalized_skin_key).exists():
        raise TeacherBuddyError("아직 잠금 해제되지 않은 스타일입니다.")
    return normalized_skin_key


def _build_selection_payload(*, user, state: TeacherBuddyState, message: str) -> dict[str, object]:
    active_key = state.active_buddy_key or state.profile_buddy_key
    profile_key = state.profile_buddy_key or state.active_buddy_key
    active_buddy = _serialize_state_buddy(
        user=user,
        state=state,
        buddy_key=active_key,
        selected_skin_key=_resolve_style_skin_key(state.active_skin_key, active_key, state.active_buddy_key),
    )
    profile_buddy = _serialize_state_buddy(
        user=user,
        state=state,
        buddy_key=profile_key,
        selected_skin_key=_resolve_style_skin_key(state.profile_skin_key, profile_key, profile_key),
    )
    collection_item = _serialize_state_buddy(
        user=user,
        state=state,
        buddy_key=active_key if active_key == profile_key else active_key,
        selected_skin_key="",
    )
    return {
        "status": "ok",
        "active_buddy": active_buddy,
        "profile_buddy": profile_buddy,
        "collection_summary_text": _collection_summary_text(user),
        "buddy_collection_summary_text": f"{TeacherBuddyUnlock.objects.filter(user=user).count()}/{TOTAL_BUDDY_COUNT} 메이트",
        "style_collection_summary_text": f"{TeacherBuddySkinUnlock.objects.filter(user=user).count()}/{TOTAL_SKIN_COUNT} 스타일",
        "sticker_dust": int(state.sticker_dust or 0),
        "message": message,
        "collection_item": collection_item,
        "buddy_progress": _build_progress_summary(
            user=user,
            state=state,
            active_buddy_payload=active_buddy,
            progress=_get_progress_for_date(user, _today()),
        ),
    }


def select_teacher_buddy(user, buddy_key: str, skin_key: str = "") -> dict[str, object]:
    if not teacher_buddy_user_is_eligible(user):
        raise TeacherBuddyError("교실 메이트는 교사 계정에서만 사용할 수 있어요.")

    normalized_key = str(buddy_key or "").strip()
    if not normalized_key:
        raise TeacherBuddyError("메이트를 먼저 골라 주세요.")

    with transaction.atomic():
        state = _get_or_create_state_for_update(user)
        state = _ensure_starter_unlocked(user=user, state=state)
        unlock = TeacherBuddyUnlock.objects.filter(user=user, buddy_key=normalized_key).first()
        if unlock is None:
            raise TeacherBuddyError("아직 잠금 해제되지 않은 메이트입니다.")
        normalized_skin_key = _validated_skin_key_for_user(user=user, buddy_key=normalized_key, skin_key=skin_key)
        state.active_buddy_key = normalized_key
        state.active_skin_key = normalized_skin_key
        state.save(update_fields=["active_buddy_key", "active_skin_key"])
        return _build_selection_payload(
            user=user,
            state=state,
            message=f"{with_particle(get_teacher_buddy(normalized_key).name, ('와', '과'))} 함께 홈을 둘러볼게요.",
        )


def select_teacher_buddy_profile(user, buddy_key: str, skin_key: str = "") -> dict[str, object]:
    if not teacher_buddy_user_is_eligible(user):
        raise TeacherBuddyError("교실 메이트는 교사 계정에서만 사용할 수 있어요.")

    normalized_key = str(buddy_key or "").strip()
    if not normalized_key:
        raise TeacherBuddyError("프로필 메이트를 먼저 골라 주세요.")

    with transaction.atomic():
        state = _get_or_create_state_for_update(user)
        state = _ensure_starter_unlocked(user=user, state=state)
        unlock = TeacherBuddyUnlock.objects.filter(user=user, buddy_key=normalized_key).first()
        if unlock is None:
            raise TeacherBuddyError("아직 잠금 해제되지 않은 메이트입니다.")
        normalized_skin_key = _validated_skin_key_for_user(user=user, buddy_key=normalized_key, skin_key=skin_key)
        state.profile_buddy_key = normalized_key
        state.profile_skin_key = normalized_skin_key
        state.save(update_fields=["profile_buddy_key", "profile_skin_key"])
        return _build_selection_payload(
            user=user,
            state=state,
            message=f"{with_particle(get_teacher_buddy(normalized_key).name, ('이', '가'))} SNS 대표 메이트가 됐어요.",
        )


def unlock_teacher_buddy_skin(user, buddy_key: str, skin_key: str) -> dict[str, object]:
    raise TeacherBuddyError("스타일은 뽑기로만 만날 수 있어요.")


def build_teacher_buddy_public_share_context(public_share_token) -> dict[str, object]:
    state = (
        TeacherBuddyState.objects.select_related("user", "user__userprofile")
        .filter(public_share_token=public_share_token)
        .first()
    )
    if state is None:
        raise TeacherBuddyError("공유 메이트를 찾지 못했어요.")

    buddy_key = state.profile_buddy_key or state.active_buddy_key
    if not buddy_key:
        raise TeacherBuddyError("공유할 대표 메이트가 아직 없어요.")

    unlock = TeacherBuddyUnlock.objects.filter(user=state.user, buddy_key=buddy_key).first()
    if unlock is None:
        raise TeacherBuddyError("공유할 대표 메이트가 아직 잠겨 있어요.")

    buddy_payload = _serialize_buddy(
        get_teacher_buddy(buddy_key),
        user=state.user,
        unlock=unlock,
        active_key=state.active_buddy_key,
        profile_key=state.profile_buddy_key or state.active_buddy_key,
        active_skin_key=_resolve_style_skin_key(state.active_skin_key, buddy_key, state.active_buddy_key),
        profile_skin_key=_resolve_style_skin_key(
            state.profile_skin_key,
            buddy_key,
            state.profile_buddy_key or state.active_buddy_key,
        ),
        selected_skin_key=_resolve_style_skin_key(
            state.profile_skin_key,
            buddy_key,
            state.profile_buddy_key or state.active_buddy_key,
        ),
    )
    nickname = _safe_nickname_for_user(state.user)
    share_path = reverse("teacher_buddy_share_page", kwargs={"public_share_token": state.public_share_token})
    share_image_path = reverse("teacher_buddy_share_image", kwargs={"public_share_token": state.public_share_token})
    share_url = f"{SITE_CANONICAL_BASE_URL}{share_path}"
    share_image_url = f"{SITE_CANONICAL_BASE_URL}{share_image_path}"
    cosmetic_key, cosmetic_label = _cosmetic_tier(int(state.sticker_dust or 0))
    return {
        "nickname": nickname,
        "buddy": buddy_payload,
        "share_copy_text": _build_share_copy_text(nickname=nickname, buddy_payload=buddy_payload),
        "share_path": share_path,
        "share_url": share_url,
        "share_image_path": share_image_path,
        "share_image_url": share_image_url,
        "sticker_dust": int(state.sticker_dust or 0),
        "cosmetic_tier": cosmetic_key,
        "cosmetic_tier_label": cosmetic_label,
    }


def _build_share_frame_svg(frame_style: str, accent: str, ring: str, tier: str) -> str:
    if frame_style == "aurora":
        return (
            f'<path d="M94 96C180 64 274 70 360 108" stroke="{accent}" stroke-width="10" stroke-linecap="round" opacity="0.55"/>'
            f'<path d="M836 516C938 468 1022 470 1104 522" stroke="{ring}" stroke-width="12" stroke-linecap="round" opacity="0.6"/>'
        )
    if frame_style == "lighthouse":
        return (
            f'<path d="M952 180L1118 108" stroke="{accent}" stroke-width="14" stroke-linecap="round" opacity="0.45"/>'
            f'<path d="M952 214L1126 214" stroke="{ring}" stroke-width="12" stroke-linecap="round" opacity="0.55"/>'
        )
    if frame_style in {"ribbon", "cabinet"}:
        return (
            f'<path d="M118 88C154 132 186 160 230 194" stroke="{accent}" stroke-width="10" stroke-linecap="round" opacity="0.5"/>'
            f'<path d="M1018 82C976 130 940 162 894 196" stroke="{ring}" stroke-width="10" stroke-linecap="round" opacity="0.5"/>'
        )
    if frame_style in {"window", "grid"}:
        return (
            f'<rect x="84" y="84" width="1032" height="462" rx="34" stroke="{ring}" stroke-width="3" opacity="0.85"/>'
            f'<path d="M600 86V544M86 315H1114" stroke="{accent}" stroke-width="2" opacity="0.18"/>'
        )
    if frame_style in {"spark", "seal", "petal"}:
        return (
            f'<circle cx="122" cy="114" r="12" fill="{accent}" opacity="0.52"/>'
            f'<circle cx="1080" cy="514" r="10" fill="{ring}" opacity="0.62"/>'
            f'<circle cx="1044" cy="112" r="7" fill="{accent}" opacity="0.4"/>'
        )
    if tier == "studio":
        return f'<rect x="82" y="82" width="1036" height="466" rx="36" stroke="{accent}" stroke-width="5" opacity="0.7"/>'
    return f'<rect x="82" y="82" width="1036" height="466" rx="36" stroke="{ring}" stroke-width="3" opacity="0.62"/>'


def build_teacher_buddy_share_svg(context: dict[str, object]) -> str:
    buddy = dict(context.get("buddy") or {})
    palette = dict(buddy.get("palette_tokens") or {})
    nickname = escape(str(context.get("nickname") or "사용자"))
    buddy_name = escape(str(buddy.get("name") or "교실 메이트"))
    rarity_label = escape(str(buddy.get("rarity_label") or "메이트"))
    caption = escape(str(buddy.get("share_caption") or "오늘도 교실 흐름을 돕고 있어요."))
    sticker_dust = int(context.get("sticker_dust") or 0)
    cosmetic_tier = str(context.get("cosmetic_tier") or "starter")
    ascii_lines = str(buddy.get("idle_ascii") or "").splitlines()[:6]
    ascii_y = 230
    ascii_markup = []
    for line in ascii_lines:
        ascii_markup.append(
            f'<text x="138" y="{ascii_y}" font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'font-size="28" font-weight="700" fill="#0f172a">{escape(line)}</text>'
        )
        ascii_y += 34

    bg_start = palette.get("bg_start", "#dbeafe")
    bg_end = palette.get("bg_end", "#e0e7ff")
    accent = palette.get("accent", "#4f46e5")
    text = palette.get("text", "#0f172a")
    ring = palette.get("ring", "#cbd5e1")
    avatar_mark = escape(str(buddy.get("avatar_mark") or "*"))
    frame_svg = _build_share_frame_svg(str(buddy.get("share_frame") or ""), accent, ring, cosmetic_tier)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" fill="none">'
        '<defs>'
        f'<linearGradient id="buddy-bg" x1="0" y1="0" x2="1200" y2="630" gradientUnits="userSpaceOnUse">'
        f'<stop stop-color="{bg_start}"/><stop offset="1" stop-color="{bg_end}"/></linearGradient>'
        '</defs>'
        f'<rect width="1200" height="630" rx="40" fill="url(#buddy-bg)"/>'
        f'<rect width="1200" height="630" rx="40" fill="white" fill-opacity="0.18"/>'
        f'<rect x="56" y="56" width="1088" height="518" rx="34" fill="white" fill-opacity="0.86"/>'
        + frame_svg
        + f'<circle cx="1030" cy="120" r="54" fill="{accent}"/>'
        f'<text x="1030" y="132" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="34" font-weight="800" fill="white">{avatar_mark}</text>'
        f'<text x="90" y="118" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700" fill="{accent}">EDUITIT 교실 메이트</text>'
        f'<text x="90" y="172" font-family="Outfit, Inter, Arial, sans-serif" font-size="54" font-weight="900" fill="{text}">{nickname}</text>'
        f'<text x="90" y="218" font-family="Inter, Arial, sans-serif" font-size="28" font-weight="800" fill="{text}">{buddy_name}</text>'
        f'<rect x="90" y="238" width="170" height="42" rx="21" fill="{ring}"/>'
        f'<text x="175" y="265" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="18" font-weight="800" fill="{text}">{rarity_label}</text>'
        f'<rect x="90" y="300" width="340" height="206" rx="28" fill="white" fill-opacity="0.92" stroke="{ring}" stroke-width="2"/>'
        + "".join(ascii_markup)
        + f'<text x="472" y="244" font-family="Inter, Arial, sans-serif" font-size="28" font-weight="700" fill="{text}">{caption}</text>'
        f'<text x="472" y="300" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700" fill="{text}">{escape(str(buddy.get("selected_skin_label") or "기본 스타일"))} · {rarity_label}</text>'
        f'<text x="472" y="354" font-family="Inter, Arial, sans-serif" font-size="18" font-weight="500" fill="{text}">우리 사이트, 카카오톡, 인스타그램에서 함께 자랑해 보세요.</text>'
        f'<rect x="472" y="410" width="510" height="80" rx="24" fill="{accent}" fill-opacity="0.12"/>'
        f'<text x="506" y="460" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="700" fill="{accent}">#{buddy_name}  #교실메이트  #Eduitit</text>'
        '</svg>'
    )
