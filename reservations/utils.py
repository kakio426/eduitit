from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import ReservationCollaborator, School


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
            "reservation_url": reverse("reservations:reservation_index", kwargs={"school_slug": school.slug}),
        })
        seen_school_ids.add(school.id)

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
