import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.utils import timezone

DATE_ABSOLUTE_PATTERN = re.compile(
    r"(?P<year>20\d{2})\s*[./-]\s*(?P<month>\d{1,2})\s*[./-]\s*(?P<day>\d{1,2})"
)
DATE_KOREAN_PATTERN = re.compile(
    r"(?P<month>\d{1,2})\s*월\s*(?P<day>\d{1,2})\s*일"
)

TIME_RANGE_COLON_PATTERN = re.compile(
    r"(?P<start_meridiem>오전|오후)?\s*(?P<start_hour>\d{1,2}):(?P<start_minute>\d{2})\s*[-~]\s*"
    r"(?P<end_meridiem>오전|오후)?\s*(?P<end_hour>\d{1,2}):(?P<end_minute>\d{2})"
)
TIME_RANGE_HOUR_PATTERN = re.compile(
    r"(?P<start_meridiem>오전|오후)?\s*(?P<start_hour>\d{1,2})\s*시(?:\s*(?P<start_minute>\d{1,2})\s*분?)?\s*[-~]\s*"
    r"(?P<end_meridiem>오전|오후)?\s*(?P<end_hour>\d{1,2})\s*시(?:\s*(?P<end_minute>\d{1,2})\s*분?)?"
)
TIME_SINGLE_COLON_PATTERN = re.compile(
    r"(?P<meridiem>오전|오후)?\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})"
)
TIME_SINGLE_HOUR_PATTERN = re.compile(
    r"(?P<meridiem>오전|오후)?\s*(?P<hour>\d{1,2})\s*시(?:\s*(?P<minute>\d{1,2})\s*분?)?"
)

RELATIVE_DATE_OFFSETS = {
    "오늘": 0,
    "내일": 1,
    "모레": 2,
    "글피": 3,
}

ALL_DAY_KEYWORDS = (
    "종일",
    "하루 종일",
    "전일",
)

HIGH_PRIORITY_KEYWORDS = (
    "긴급",
    "중요",
    "필수",
    "마감",
    "오늘까지",
    "즉시",
)

LOW_PRIORITY_KEYWORDS = (
    "참고",
    "여유",
    "나중",
)

TODO_HINT_KEYWORDS = (
    "준비",
    "제출",
    "가져",
    "챙기",
    "신청",
    "확인",
    "완료",
)

AMBIGUOUS_HINT_KEYWORDS = (
    "미정",
    "추후",
    "가능하면",
    "예정",
)


def _normalize_text(raw_text):
    normalized = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    return "\n".join(lines), lines


def _safe_date(year, month, day):
    try:
        return date(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None


def _parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_hour_with_meridiem(hour, meridiem):
    hour_value = _parse_int(hour, -1)
    if hour_value < 0:
        return None, False
    meridiem = (meridiem or "").strip()
    if meridiem == "오전":
        if hour_value == 12:
            return 0, False
        return hour_value, False
    if meridiem == "오후":
        if 1 <= hour_value <= 11:
            return hour_value + 12, False
        return hour_value, False

    # 오전/오후 미기재: 학교 공지 맥락에서 1~7시는 오후로 추정하고 낮은 신뢰도로 표시.
    if 1 <= hour_value <= 7:
        return hour_value + 12, True
    if 0 <= hour_value <= 23:
        return hour_value, False
    return hour_value, True


def _build_time(hour, minute, meridiem):
    hour_value, ambiguous = _normalize_hour_with_meridiem(hour, meridiem)
    minute_value = _parse_int(minute, 0)
    if hour_value is None or hour_value < 0 or hour_value > 23:
        return None, ambiguous
    if minute_value < 0 or minute_value > 59:
        return None, ambiguous
    return time(hour=hour_value, minute=minute_value), ambiguous


def _extract_date(text, now_date):
    candidates = []

    for match in DATE_ABSOLUTE_PATTERN.finditer(text):
        matched_date = _safe_date(
            match.group("year"),
            match.group("month"),
            match.group("day"),
        )
        if matched_date:
            candidates.append(
                {
                    "position": match.start(),
                    "value": matched_date,
                    "evidence": match.group(0),
                    "is_relative": False,
                    "year_inferred": False,
                }
            )

    for match in DATE_KOREAN_PATTERN.finditer(text):
        month = _parse_int(match.group("month"), 0)
        day = _parse_int(match.group("day"), 0)
        candidate = _safe_date(now_date.year, month, day)
        if not candidate:
            continue
        year_inferred = False
        if candidate < (now_date - timedelta(days=7)):
            candidate = _safe_date(now_date.year + 1, month, day) or candidate
            year_inferred = True
        candidates.append(
            {
                "position": match.start(),
                "value": candidate,
                "evidence": match.group(0),
                "is_relative": False,
                "year_inferred": year_inferred,
            }
        )

    for keyword, offset in RELATIVE_DATE_OFFSETS.items():
        position = text.find(keyword)
        if position < 0:
            continue
        candidates.append(
            {
                "position": position,
                "value": now_date + timedelta(days=offset),
                "evidence": keyword,
                "is_relative": True,
                "year_inferred": False,
            }
        )

    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item["position"])[0]


def _extract_time(text):
    if any(keyword in text for keyword in ALL_DAY_KEYWORDS):
        return {
            "is_all_day": True,
            "start": time(hour=0, minute=0),
            "end": time(hour=23, minute=59),
            "evidence": "종일",
            "ambiguous": False,
        }

    for pattern in (TIME_RANGE_COLON_PATTERN, TIME_RANGE_HOUR_PATTERN):
        match = pattern.search(text)
        if not match:
            continue
        start_clock, start_ambiguous = _build_time(
            match.group("start_hour"),
            match.group("start_minute"),
            match.group("start_meridiem"),
        )
        end_clock, end_ambiguous = _build_time(
            match.group("end_hour"),
            match.group("end_minute"),
            match.group("end_meridiem"),
        )
        if not start_clock or not end_clock:
            continue
        if datetime.combine(date.today(), end_clock) <= datetime.combine(date.today(), start_clock):
            continue
        return {
            "is_all_day": False,
            "start": start_clock,
            "end": end_clock,
            "evidence": match.group(0),
            "ambiguous": bool(start_ambiguous or end_ambiguous),
        }

    for pattern in (TIME_SINGLE_COLON_PATTERN, TIME_SINGLE_HOUR_PATTERN):
        match = pattern.search(text)
        if not match:
            continue
        start_clock, ambiguous = _build_time(
            match.group("hour"),
            match.group("minute"),
            match.group("meridiem"),
        )
        if not start_clock:
            continue
        start_dt = datetime.combine(date.today(), start_clock)
        end_dt = start_dt + timedelta(hours=1)
        return {
            "is_all_day": False,
            "start": start_clock,
            "end": end_dt.time().replace(second=0, microsecond=0),
            "evidence": match.group(0),
            "ambiguous": bool(ambiguous),
        }

    return None


def _extract_priority(text):
    lowered = text.lower()
    for keyword in HIGH_PRIORITY_KEYWORDS:
        if keyword.lower() in lowered:
            return "high", keyword
    for keyword in LOW_PRIORITY_KEYWORDS:
        if keyword.lower() in lowered:
            return "low", keyword
    return "normal", ""


def _build_title(lines):
    if not lines:
        return ""
    first_line = lines[0]
    if len(first_line) <= 200:
        return first_line
    return first_line[:200].rstrip()


def _build_todo_summary(lines, title):
    if not lines:
        return ""

    candidates = []
    for line in lines:
        if line == title:
            continue
        if line.startswith(("-", "•", "*")):
            candidates.append(line.lstrip("-•* ").strip())
            continue
        if any(keyword in line for keyword in TODO_HINT_KEYWORDS):
            candidates.append(line)

    if not candidates:
        body_lines = [line for line in lines if line != title]
        candidates = body_lines[:2]

    joined = "\n".join(candidates).strip()
    return joined[:5000]


def _calculate_confidence(
    *,
    has_title,
    has_date,
    has_time,
    has_todo,
    has_files,
    relative_date,
    year_inferred,
    ambiguous_time,
    ambiguous_hint,
):
    score = 30
    if has_title:
        score += 20
    else:
        score -= 10

    if has_date:
        score += 25
    else:
        score -= 20

    if has_time:
        score += 15
    else:
        score -= 5

    if has_todo:
        score += 5
    if has_files:
        score += 5
    if relative_date:
        score -= 6
    if year_inferred:
        score -= 6
    if ambiguous_time:
        score -= 12
    if ambiguous_hint:
        score -= 10

    score = max(0, min(99, score))
    return Decimal(str(score)).quantize(Decimal("0.01"))


def _confidence_label(score):
    score_value = float(score or 0)
    if score_value >= 80:
        return "high"
    if score_value >= 55:
        return "medium"
    return "low"


def parse_message_capture_draft(raw_text, *, now=None, has_files=False):
    now = now or timezone.now()
    normalized_text, lines = _normalize_text(raw_text)
    parsed_date = _extract_date(normalized_text, timezone.localtime(now).date())
    parsed_time = _extract_time(normalized_text)
    title = _build_title(lines)
    todo_summary = _build_todo_summary(lines, title)
    extracted_priority, priority_evidence = _extract_priority(normalized_text)
    has_ambiguous_hint = any(keyword in normalized_text for keyword in AMBIGUOUS_HINT_KEYWORDS)

    start_at = None
    end_at = None
    is_all_day = False
    if parsed_date and parsed_time:
        is_all_day = bool(parsed_time["is_all_day"])
        start_naive = datetime.combine(parsed_date["value"], parsed_time["start"])
        end_naive = datetime.combine(parsed_date["value"], parsed_time["end"])
        local_tz = timezone.get_current_timezone()
        start_at = timezone.make_aware(start_naive, local_tz)
        end_at = timezone.make_aware(end_naive, local_tz)

    has_title = bool(title)
    has_date = bool(parsed_date)
    has_time = bool(parsed_time)
    has_todo = bool(todo_summary)
    confidence_score = _calculate_confidence(
        has_title=has_title,
        has_date=has_date,
        has_time=has_time,
        has_todo=has_todo,
        has_files=has_files,
        relative_date=bool(parsed_date and parsed_date["is_relative"]),
        year_inferred=bool(parsed_date and parsed_date["year_inferred"]),
        ambiguous_time=bool(parsed_time and parsed_time["ambiguous"]),
        ambiguous_hint=has_ambiguous_hint,
    )
    confidence_label = _confidence_label(confidence_score)

    has_ambiguity = bool(
        (parsed_date and (parsed_date["is_relative"] or parsed_date["year_inferred"]))
        or (parsed_time and parsed_time["ambiguous"])
        or has_ambiguous_hint
    )
    if has_title and has_date and has_time and not has_ambiguity:
        parse_status = "parsed"
    elif has_title or has_date or has_time or has_todo or has_files:
        parse_status = "needs_review"
    else:
        parse_status = "failed"

    warnings = []
    if not has_title:
        warnings.append("제목을 자동으로 찾지 못해 직접 확인이 필요합니다.")
    if not has_date:
        warnings.append("날짜를 자동으로 찾지 못해 직접 선택이 필요합니다.")
    if not has_time:
        warnings.append("시간을 자동으로 찾지 못해 직접 입력이 필요합니다.")
    if parsed_date and parsed_date["is_relative"]:
        warnings.append("상대 날짜 표현을 사용해 날짜 확인이 필요합니다.")
    if parsed_date and parsed_date["year_inferred"]:
        warnings.append("연도가 없어 내년 일정으로 추정했는지 확인해 주세요.")
    if parsed_time and parsed_time["ambiguous"]:
        warnings.append("오전/오후 표현이 없어 시간 확인이 필요합니다.")
    if has_ambiguous_hint:
        warnings.append("미정/추후 표현이 있어 일정 확정 여부를 확인해 주세요.")
    if parse_status == "failed":
        warnings = ["일정 정보를 자동으로 읽지 못했습니다. 제목과 날짜를 직접 입력해 주세요."]

    return {
        "normalized_text": normalized_text,
        "parse_status": parse_status,
        "confidence_score": confidence_score,
        "confidence_label": confidence_label,
        "extracted_title": title or "메시지에서 만든 일정",
        "extracted_start_time": start_at,
        "extracted_end_time": end_at,
        "extracted_is_all_day": is_all_day,
        "extracted_priority": extracted_priority,
        "extracted_todo_summary": todo_summary,
        "warnings": warnings,
        "evidence": {
            "date": parsed_date["evidence"] if parsed_date else "",
            "time": parsed_time["evidence"] if parsed_time else "",
            "priority": priority_evidence,
        },
    }
