from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from core.models import UserProfile
from .models import ReservationCollaborator, School

RECENT_RESERVATION_SCHOOL_LIMIT = 6


def _get_or_create_profile_for_user(user):
    if not getattr(user, "is_authenticated", False):
        return None
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _normalize_recent_reservation_school_ids(raw_value):
    normalized = []
    seen_school_ids = set()
    for value in raw_value if isinstance(raw_value, list) else []:
        try:
            school_id = int(value)
        except (TypeError, ValueError):
            continue
        if school_id < 1 or school_id in seen_school_ids:
            continue
        normalized.append(school_id)
        seen_school_ids.add(school_id)
        if len(normalized) >= RECENT_RESERVATION_SCHOOL_LIMIT:
            break
    return normalized


def _get_recent_reservation_school_ids_for_user(user):
    profile = _get_or_create_profile_for_user(user)
    if profile is None:
        return None, []

    school_ids = _normalize_recent_reservation_school_ids(profile.recent_reservation_school_ids)
    if profile.recent_reservation_school_ids != school_ids:
        profile.recent_reservation_school_ids = school_ids
        profile.save(update_fields=["recent_reservation_school_ids"])
    return profile, school_ids


def remember_recent_reservation_school(user, school):
    if not getattr(user, "is_authenticated", False) or school is None:
        return []

    profile, school_ids = _get_recent_reservation_school_ids_for_user(user)
    if profile is None:
        return []

    next_school_ids = [school.id, *[school_id for school_id in school_ids if school_id != school.id]]
    next_school_ids = next_school_ids[:RECENT_RESERVATION_SCHOOL_LIMIT]
    if next_school_ids != school_ids:
        profile.recent_reservation_school_ids = next_school_ids
        profile.save(update_fields=["recent_reservation_school_ids"])
    return next_school_ids


def _build_recent_reservation_school_entries(user, *, exclude_school_ids=None):
    profile, school_ids = _get_recent_reservation_school_ids_for_user(user)
    if profile is None or not school_ids:
        return []

    school_map = School.objects.filter(id__in=school_ids).only("id", "name", "slug").in_bulk()
    resolved_school_ids = [school_id for school_id in school_ids if school_id in school_map]
    if resolved_school_ids != school_ids:
        profile.recent_reservation_school_ids = resolved_school_ids
        profile.save(update_fields=["recent_reservation_school_ids"])

    excluded_ids = set(exclude_school_ids or ())
    entries = []
    for school_id in resolved_school_ids:
        if school_id in excluded_ids:
            continue
        school = school_map[school_id]
        entries.append({
            "school": school,
            "role": "recent",
            "role_label": "최근 사용",
            "role_tone": "amber",
            "summary": "로그인 후 링크로 열어본 예약판",
            "can_edit": True,
            "owner_name": "",
            "reservation_url": reverse("reservations:reservation_index", kwargs={"school_slug": school.slug}),
        })
    return entries


def list_user_accessible_schools(user):
    """Return the schools that a logged-in user can reopen from home."""
    if not getattr(user, "is_authenticated", False):
        return []

    entries = []
    seen_school_ids = set()

    owned_schools = (
        School.objects.filter(owner=user)
        .only("id", "name", "slug")
        .order_by("name")
    )
    for school in owned_schools:
        entries.append({
            "school": school,
            "role": "owner",
            "role_label": "관리자",
            "role_tone": "violet",
            "summary": "내가 관리하는 예약판",
            "can_edit": True,
            "owner_name": "",
            "reservation_url": reverse("reservations:reservation_index", kwargs={"school_slug": school.slug}),
        })
        seen_school_ids.add(school.id)

    shared_relations = (
        ReservationCollaborator.objects.filter(collaborator=user)
        .select_related("school", "school__owner")
        .order_by("school__name")
    )
    for relation in shared_relations:
        school = relation.school
        if school.id in seen_school_ids:
            continue
        owner_name = school.owner.get_full_name() or school.owner.username
        entries.append({
            "school": school,
            "role": "edit" if relation.can_edit else "view",
            "role_label": "편집 가능" if relation.can_edit else "읽기 전용",
            "role_tone": "emerald" if relation.can_edit else "slate",
            "summary": f"{owner_name} 선생님이 공유한 예약판",
            "can_edit": bool(relation.can_edit),
            "owner_name": owner_name,
            "reservation_url": reverse("reservations:reservation_index", kwargs={"school_slug": school.slug}),
        })
        seen_school_ids.add(school.id)

    entries.extend(
        _build_recent_reservation_school_entries(
            user,
            exclude_school_ids=seen_school_ids,
        )
    )

    return entries


def resolve_user_reservation_entry_url(user):
    """Open the reservation board directly when the user has only one linked school."""
    accessible_schools = list_user_accessible_schools(user)
    if len(accessible_schools) == 1:
        return accessible_schools[0]["reservation_url"]
    return reverse("reservations:dashboard_landing")

def get_max_booking_date(school):
    """
    학교의 '주간 예약 제한 모드' 설정에 따라 예약 가능한 최대 날짜를 반환합니다.
    
    Logic:
    1. weekly_opening_mode == False: None (제한 없음)
    2. weekly_opening_mode == True:
       - 이번 주의 '오픈 시간'(예: 금요일 09:00)을 계산합니다.
       - 현재 시간이 오픈 시간 '이전'이면: 이번 주 일요일까지만 예약 가능.
       - 현재 시간이 오픈 시간 '이후'이면: 다음 주 일요일까지 예약 가능.
    """
    if not school.config.weekly_opening_mode:
        return None

    now = timezone.localtime()
    today = now.date()
    
    # 0=월, 6=일
    current_weekday = today.weekday()
    target_weekday = school.config.weekly_opening_weekday
    target_hour = school.config.weekly_opening_hour
    
    # 이번 주의 타겟 요일 날짜 계산
    # 예: 오늘(수, 2) -> 타겟(금, 4) => +2일
    # 예: 오늘(토, 5) -> 타겟(금, 4) => -1일 (어제였음)
    days_diff = target_weekday - current_weekday
    target_date = today + timedelta(days=days_diff)
    
    # 타겟 날짜/시간 생성 (timezone-aware)
    target_dt = timezone.make_aware(timezone.datetime.combine(
        target_date, 
        timezone.datetime.min.time().replace(hour=target_hour)
    ))
    
    # 이번 주 일요일 (이번 주 마지막 날)
    # weekday: 0(Mon)..6(Sun) -> 6 - current = days until Sunday
    this_sunday = today + timedelta(days=(6 - current_weekday))
    
    if now < target_dt:
        # 아직 오픈 시간이 안 됨 -> 이번 주 일요일까지만
        return this_sunday
    else:
        # 오픈 시간 지남 -> 다음 주 일요일까지
        return this_sunday + timedelta(days=7)
