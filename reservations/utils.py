from django.utils import timezone
from datetime import timedelta

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
