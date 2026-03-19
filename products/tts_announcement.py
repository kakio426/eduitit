from datetime import datetime, time, timedelta
from types import SimpleNamespace

from django.utils import timezone


ANNOUNCEMENT_OFFSET_MINUTES = 5
DEFAULT_DEMO_ROWS = (
    SimpleNamespace(period=1, subject="과학", start_time=time(8, 55), end_time=time(9, 35), id="demo-1"),
    SimpleNamespace(period=2, subject="수학", start_time=time(9, 45), end_time=time(10, 25), id="demo-2"),
    SimpleNamespace(period=3, subject="국어", start_time=time(10, 35), end_time=time(11, 15), id="demo-3"),
    SimpleNamespace(period=4, subject="사회", start_time=time(11, 25), end_time=time(12, 5), id="demo-4"),
)


def _period_label(period):
    try:
        period_number = int(period)
    except (TypeError, ValueError):
        period_number = str(period or "").strip()
        return f"{period_number}교시" if period_number else "교시"
    return f"{period_number}교시"


def _time_label(value):
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value or "")


def _delta_label(delta):
    total_seconds = max(0, int(delta.total_seconds()))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        if minutes:
            return f"{hours}시간 {minutes}분"
        return f"{hours}시간"
    if minutes:
        return f"{minutes}분"
    return f"{seconds}초"


def build_tts_announcement_text(period, subject, *, minutes_before=ANNOUNCEMENT_OFFSET_MINUTES):
    period_label = _period_label(period)
    subject_text = str(subject or "").strip() or "수업"
    if minutes_before and minutes_before > 0:
        return f"{period_label} {minutes_before}분 전입니다. {period_label}는 {subject_text}입니다!"
    return f"{period_label}는 {subject_text}입니다!"


def _row_to_dict(row, *, date, minutes_before, is_demo=False):
    period = getattr(row, "period", None)
    subject = str(getattr(row, "subject", "") or "").strip() or "수업"
    start_time = getattr(row, "start_time", None)
    end_time = getattr(row, "end_time", None)
    period_label = _period_label(period)

    start_dt = timezone.make_aware(datetime.combine(date, start_time), timezone.get_current_timezone())
    announce_dt = start_dt - timedelta(minutes=minutes_before)
    end_dt = timezone.make_aware(datetime.combine(date, end_time), timezone.get_current_timezone())

    return {
        "id": f"{'demo' if is_demo else 'schedule'}-{getattr(row, 'id', getattr(row, 'pk', period))}",
        "period": period,
        "period_label": period_label,
        "subject": subject,
        "start_time_label": _time_label(start_time),
        "end_time_label": _time_label(end_time),
        "announce_time_label": announce_dt.strftime("%H:%M"),
        "announcement_text": build_tts_announcement_text(period, subject, minutes_before=minutes_before),
        "announce_at_iso": announce_dt.isoformat(),
        "start_at_iso": start_dt.isoformat(),
        "end_at_iso": end_dt.isoformat(),
        "minutes_before": minutes_before,
        "is_demo": is_demo,
    }


def build_tts_announcement_rows(schedule_rows, *, date=None, minutes_before=ANNOUNCEMENT_OFFSET_MINUTES, is_demo=False):
    if date is None:
        date = timezone.localdate()

    ordered_rows = sorted(
        list(schedule_rows),
        key=lambda row: (
            int(getattr(row, "period", 0) or 0),
            str(getattr(row, "id", 0) or 0),
        ),
    )
    return [
        _row_to_dict(row, date=date, minutes_before=minutes_before, is_demo=is_demo)
        for row in ordered_rows
    ]


def build_demo_tts_rows(*, date=None, minutes_before=ANNOUNCEMENT_OFFSET_MINUTES):
    if date is None:
        date = timezone.localdate()
    return build_tts_announcement_rows(DEFAULT_DEMO_ROWS, date=date, minutes_before=minutes_before, is_demo=True)


def annotate_tts_rows(rows, *, now=None):
    if now is None:
        now = timezone.localtime()

    next_row_index = None
    for index, row in enumerate(rows):
        announce_at = datetime.fromisoformat(row["announce_at_iso"])
        start_at = datetime.fromisoformat(row["start_at_iso"])
        if timezone.is_naive(announce_at):
            announce_at = timezone.make_aware(announce_at, timezone.get_current_timezone())
        if timezone.is_naive(start_at):
            start_at = timezone.make_aware(start_at, timezone.get_current_timezone())

        if next_row_index is None and now <= announce_at:
            next_row_index = index

        if now < announce_at:
            row["status_label"] = "안내 예정"
            row["countdown_label"] = f"{_delta_label(announce_at - now)} 뒤 방송"
            row["status_tone"] = "future"
        elif now < start_at:
            row["status_label"] = "지금 읽기"
            row["countdown_label"] = f"{_delta_label(start_at - now)} 뒤 수업 시작"
            row["status_tone"] = "ready"
            if next_row_index is None:
                next_row_index = index
        else:
            row["status_label"] = "완료"
            row["countdown_label"] = f"{_delta_label(now - start_at)} 지남"
            row["status_tone"] = "past"

        row["is_next"] = False

    if next_row_index is None and rows:
        next_row_index = len(rows) - 1

    if next_row_index is not None:
        rows[next_row_index]["is_next"] = True

    return rows
