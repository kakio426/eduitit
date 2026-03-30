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

DEFAULT_BROADCAST_GROUPS = (
    {
        "id": "start",
        "title": "수업 시작",
        "description": "첫 집중을 잡고 수업을 시작할 때 씁니다.",
        "items": (
            {
                "id": "start-ready",
                "title": "수업 준비",
                "summary": "앉기, 준비물 꺼내기, 시작 준비",
                "message": "{audience}, 이제 수업을 시작하겠습니다. 자리에 바르게 앉고 필요한 준비물을 꺼내 주세요.",
            },
            {
                "id": "start-focus",
                "title": "앞을 보기",
                "summary": "하던 일을 멈추고 설명에 집중시키기",
                "message": "{audience}, 잠시 하던 활동을 멈추고 앞을 봐 주세요. 지금부터 중요한 설명을 하겠습니다.",
            },
        ),
    },
    {
        "id": "activity",
        "title": "활동 안내",
        "description": "모둠 활동이나 실습 시작 안내에 맞춥니다.",
        "items": (
            {
                "id": "activity-group",
                "title": "모둠 활동 시작",
                "summary": "역할을 나누고 함께 시작하기",
                "message": "{audience}, 지금부터 모둠 활동을 시작합니다. 역할을 정하고 활동지를 펼친 뒤 함께 시작해 주세요.",
            },
            {
                "id": "activity-practice",
                "title": "실습 준비",
                "summary": "설명 뒤 차례대로 시작시키기",
                "message": "{audience}, 준비물을 꺼내고 설명을 들은 뒤 차례대로 시작해 주세요. 도움이 필요하면 손을 들어 주세요.",
            },
        ),
    },
    {
        "id": "focus",
        "title": "집중 회복",
        "description": "교실이 조금 산만해졌을 때 바로 씁니다.",
        "items": (
            {
                "id": "focus-quiet",
                "title": "조용히 모이기",
                "summary": "목소리를 줄이고 집중시키기",
                "message": "{audience}, 목소리를 줄이고 제 신호에 맞춰 집중해 주세요. 지금부터 함께 확인하겠습니다.",
            },
            {
                "id": "focus-wait",
                "title": "정리 후 대기",
                "summary": "손을 멈추고 차분히 기다리기",
                "message": "{audience}, 하던 일을 멈추고 책상 위를 정리한 뒤 조용히 기다려 주세요. 곧 다음 안내를 드리겠습니다.",
            },
        ),
    },
    {
        "id": "finish",
        "title": "정리와 마무리",
        "description": "과제 확인과 퇴실 준비를 도와줍니다.",
        "items": (
            {
                "id": "finish-homework",
                "title": "과제 확인",
                "summary": "오늘 할 일과 제출물을 점검하기",
                "message": "{audience}, 오늘 수업을 정리합니다. 과제와 준비물을 확인하고 제출할 것은 앞에 내 주세요.",
            },
            {
                "id": "finish-dismiss",
                "title": "퇴실 준비",
                "summary": "자리와 주변을 정돈한 뒤 이동하기",
                "message": "{audience}, 의자와 책상을 정돈하고 주변을 확인한 뒤 천천히 이동해 주세요.",
            },
        ),
    },
    {
        "id": "safety",
        "title": "생활과 안전",
        "description": "이동, 질서, 격려 방송에 맞춥니다.",
        "items": (
            {
                "id": "safety-move",
                "title": "이동 안내",
                "summary": "복도, 특별실, 급식실 이동 전에 읽기",
                "message": "{audience}, 뛰지 말고 앞사람과 간격을 유지하면서 천천히 이동합니다. 주변 친구도 함께 살펴 주세요.",
            },
            {
                "id": "safety-praise",
                "title": "칭찬과 격려",
                "summary": "차분한 분위기를 이어 갈 때",
                "message": "{audience}, 지금처럼 차분하게 참여해 줘서 고맙습니다. 이 분위기로 끝까지 함께해 주세요.",
            },
        ),
    },
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


def build_tts_broadcast_template_groups(classroom_name=""):
    name = str(classroom_name or "").strip()
    audience = f"{name} 여러분" if name and name != "데모 학급" else "여러분"
    groups = []

    for group in DEFAULT_BROADCAST_GROUPS:
        group_items = []
        for item in group["items"]:
            group_items.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "summary": item["summary"],
                    "message": item["message"].format(audience=audience),
                }
            )

        groups.append(
            {
                "id": group["id"],
                "title": group["title"],
                "description": group["description"],
                "items": group_items,
            }
        )

    return groups


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
