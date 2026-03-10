import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.utils import timezone

DATE_ABSOLUTE_PATTERN = re.compile(
    r"(?P<year>20\d{2})\s*[./-]\s*(?P<month>\d{1,2})\s*[./-]\s*(?P<day>\d{1,2})"
)
DATE_KOREAN_PATTERN = re.compile(
    r"(?P<month>\d{1,2})\s*월\s*(?P<day>\d{1,2})\s*일(?:\([월화수목금토일]\))?"
)
DAY_ONLY_KOREAN_PATTERN = re.compile(
    r"(?P<day>\d{1,2})\s*일(?:\([월화수목금토일]\))?"
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
LEADING_DATE_PREFIX_PATTERN = re.compile(
    r"^\s*(?:(?:20\d{2}\s*[./-]\s*)?\d{1,2}\s*(?:[./-]|월)\s*\d{1,2}\s*일?(?:\([월화수목금토일]\))?|\d{1,2}\s*일(?:\([월화수목금토일]\))?)\s*(?:에|까지|부터)?\s*"
)
MATERIALS_PATTERN = re.compile(r"준비물\s*[:：]?\s*(?P<value>.+)")
AUDIENCE_PATTERN = re.compile(r"(?P<value>\d+학년(?:\s*\d+반)?|학부모|전교생|교직원|학생회|학생)")
RECURRENCE_PATTERN = re.compile(r"(?P<value>매주|매월|격주|매일|매 학기|매 학년)")
LOCATION_POSTFIX_PATTERN = re.compile(r"(?P<value>[가-힣A-Za-z0-9\s]{1,24}(?:실|관|장|센터|교실|강당|도서관|회의실))(?:에서|으로|로)")

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
    "작성",
    "수정",
    "회신",
    "부탁",
)

TASK_HINT_KEYWORDS = (
    "제출",
    "준비",
    "챙기기",
    "마감",
    "신청",
    "확인",
    "완료",
    "까지",
    "수정",
    "작성",
    "회신",
    "부탁",
)

EVENT_HINT_KEYWORDS = (
    "회의",
    "상담",
    "수업",
    "설명회",
    "연수",
    "행사",
    "체험학습",
    "모임",
    "발표",
    "총회",
    "학부모총회",
)

PREP_HINT_KEYWORDS = (
    "준비",
    "사전",
    "배부",
    "탑재",
    "공유",
    "정리",
)

CATEGORY_KEYWORDS = {
    "meeting": ("회의", "협의", "모임"),
    "consulting": ("상담",),
    "class": ("수업", "강의"),
    "training": ("연수",),
    "event": ("행사", "체험학습", "설명회", "발표", "총회"),
    "submission": ("제출", "마감", "신청", "회신"),
}

AMBIGUOUS_HINT_KEYWORDS = (
    "미정",
    "추후",
    "가능하면",
    "예정",
)

GREETING_PREFIXES = (
    "선생님안녕하세요",
    "안녕하세요",
    "안녕하십니까",
    "수고하십니다",
    "수고많으십니다",
)

TASK_ACTION_KEYWORDS = (
    "수정",
    "작성",
    "제출",
    "회신",
    "검토",
    "작업",
    "부탁",
    "알려주시면",
    "안내",
    "탑재",
    "공유",
    "배부",
)

TASK_OBJECT_KEYWORDS = (
    "연수물",
    "안내문",
    "가정통신문",
    "자료",
    "문서",
    "파일",
    "보고서",
    "계획서",
    "명단",
    "신청서",
    "동의서",
    "안내장",
)

TITLE_CONTEXT_KEYWORDS = (
    "학부모총회",
    "총회",
    "설명회",
    "연수",
    "회의",
    "상담",
    "행사",
    "발표",
    "수업",
)

DEADLINE_HINT_KEYWORDS = (
    "까지",
    "마감",
    "제출",
    "수정",
    "작성",
    "회신",
    "부탁",
    "완료",
)

KNOWN_LOCATIONS = (
    "과학실",
    "교무실",
    "상담실",
    "체육관",
    "운동장",
    "강당",
    "도서관",
    "시청각실",
    "회의실",
    "방송실",
)

KIND_EVENT = "event"
KIND_DEADLINE = "deadline"
KIND_PREP = "prep"



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



def _extract_materials(lines):
    for line in lines:
        match = MATERIALS_PATTERN.search(line)
        if match:
            return match.group("value").strip()[:500]
    return ""



def _extract_location(text, lines):
    match = LOCATION_POSTFIX_PATTERN.search(text)
    if match:
        return match.group("value").strip()[:120]
    for location in KNOWN_LOCATIONS:
        if location in text:
            return location
    for line in lines:
        if "장소" in line or "위치" in line:
            return line.replace("장소", "").replace("위치", "").replace(":", "").strip()[:120]
    return ""



def _extract_audience(text):
    match = AUDIENCE_PATTERN.search(text)
    if not match:
        return ""
    return match.group("value").strip()[:120]



def _extract_category(text):
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return ""



def _extract_recurrence_hint(text):
    match = RECURRENCE_PATTERN.search(text)
    if not match:
        return ""
    return match.group("value")



def _is_greeting_line(line):
    compact = re.sub(r"\s+", "", line or "")
    compact = compact.strip(".!?,:; ")
    return any(compact.startswith(prefix) for prefix in GREETING_PREFIXES)



def _strip_date_prefix(line):
    cleaned = LEADING_DATE_PREFIX_PATTERN.sub("", line or "").strip()
    return cleaned.lstrip("-•*:,.) ").rstrip(".! ")



def _extract_context_keyword(text):
    for keyword in TITLE_CONTEXT_KEYWORDS:
        if keyword in text:
            return keyword
    return ""



def _extract_object_keyword(text):
    for keyword in TASK_OBJECT_KEYWORDS:
        if keyword in text:
            return keyword
    return ""



def _extract_action_keyword(text):
    for keyword in TASK_ACTION_KEYWORDS:
        if keyword in text:
            return keyword
    return ""



def _count_keyword_hits(text, keywords):
    return sum(1 for keyword in keywords if keyword in text)



def _calculate_confidence(*, has_title, has_date, has_time, has_summary, relative_date, inferred_date, ambiguous_time):
    score = 40
    if has_title:
        score += 18
    if has_date:
        score += 22
    if has_time:
        score += 8
    if has_summary:
        score += 8
    if relative_date:
        score -= 6
    if inferred_date:
        score -= 8
    if ambiguous_time:
        score -= 10
    score = max(0, min(99, score))
    return Decimal(str(score)).quantize(Decimal("0.01"))



def _confidence_label(score):
    value = float(score or 0)
    if value >= 80:
        return "high"
    if value >= 55:
        return "medium"
    return "low"



def _infer_candidate_kind(base_text, support_text):
    primary_text = str(base_text or "")
    combined_text = "\n".join([primary_text, str(support_text or "")]).strip()
    if any(keyword in primary_text for keyword in DEADLINE_HINT_KEYWORDS):
        return KIND_DEADLINE
    if any(keyword in primary_text for keyword in PREP_HINT_KEYWORDS):
        return KIND_PREP
    if any(keyword in primary_text for keyword in EVENT_HINT_KEYWORDS):
        return KIND_EVENT
    if any(keyword in combined_text for keyword in DEADLINE_HINT_KEYWORDS):
        return KIND_DEADLINE
    if any(keyword in combined_text for keyword in PREP_HINT_KEYWORDS):
        return KIND_PREP
    return KIND_EVENT



def _infer_line_date_mentions(lines, now_date):
    date_mentions = []
    current_month = now_date.month
    current_year = now_date.year

    for line_index, line in enumerate(lines):
        line_mentions = []
        for match in DATE_ABSOLUTE_PATTERN.finditer(line):
            matched_date = _safe_date(match.group("year"), match.group("month"), match.group("day"))
            if not matched_date:
                continue
            current_month = matched_date.month
            current_year = matched_date.year
            line_mentions.append(
                {
                    "line_index": line_index,
                    "position": match.start(),
                    "value": matched_date,
                    "evidence": match.group(0),
                    "is_relative": False,
                    "year_inferred": False,
                    "month_inferred": False,
                }
            )

        for match in DATE_KOREAN_PATTERN.finditer(line):
            month = _parse_int(match.group("month"), current_month)
            day = _parse_int(match.group("day"), 0)
            matched_date = _safe_date(current_year, month, day)
            if not matched_date:
                continue
            year_inferred = False
            if matched_date < (now_date - timedelta(days=7)):
                rolled = _safe_date(current_year + 1, month, day)
                if rolled:
                    matched_date = rolled
                    year_inferred = True
            current_month = matched_date.month
            current_year = matched_date.year
            line_mentions.append(
                {
                    "line_index": line_index,
                    "position": match.start(),
                    "value": matched_date,
                    "evidence": match.group(0),
                    "is_relative": False,
                    "year_inferred": year_inferred,
                    "month_inferred": False,
                }
            )

        for match in DAY_ONLY_KOREAN_PATTERN.finditer(line):
            prefix = line[max(0, match.start() - 4):match.start()]
            if "월" in prefix:
                continue
            day = _parse_int(match.group("day"), 0)
            matched_date = _safe_date(current_year, current_month, day)
            if not matched_date:
                continue
            month_inferred = False
            year_inferred = False
            if matched_date < (now_date - timedelta(days=7)):
                next_month = current_month + 1
                next_year = current_year
                if next_month > 12:
                    next_month = 1
                    next_year += 1
                rolled = _safe_date(next_year, next_month, day)
                if rolled:
                    matched_date = rolled
                    month_inferred = True
                    year_inferred = next_year != current_year
            line_mentions.append(
                {
                    "line_index": line_index,
                    "position": match.start(),
                    "value": matched_date,
                    "evidence": match.group(0),
                    "is_relative": False,
                    "year_inferred": year_inferred,
                    "month_inferred": month_inferred,
                }
            )

        for keyword, offset in RELATIVE_DATE_OFFSETS.items():
            position = line.find(keyword)
            if position < 0:
                continue
            line_mentions.append(
                {
                    "line_index": line_index,
                    "position": position,
                    "value": now_date + timedelta(days=offset),
                    "evidence": keyword,
                    "is_relative": True,
                    "year_inferred": False,
                    "month_inferred": False,
                }
            )

        line_mentions.sort(key=lambda item: item["position"])
        date_mentions.extend(line_mentions)

    return date_mentions



def _lines_with_date_mentions(date_mentions):
    return {item["line_index"] for item in date_mentions}



def _collect_support_lines(lines, date_mentions, mention, window=5):
    line_indexes_with_dates = _lines_with_date_mentions(date_mentions)
    current_index = mention["line_index"]
    collected = [current_index]

    for step in range(1, window + 1):
        previous_index = current_index - step
        if previous_index < 0:
            break
        if previous_index in line_indexes_with_dates:
            break
        previous_line = lines[previous_index]
        if _is_greeting_line(previous_line):
            continue
        if any(keyword in previous_line for keyword in TASK_ACTION_KEYWORDS + TASK_OBJECT_KEYWORDS + EVENT_HINT_KEYWORDS + PREP_HINT_KEYWORDS):
            collected.insert(0, previous_index)
        elif step == 1 and len(previous_line) <= 40:
            collected.insert(0, previous_index)

    for step in range(1, window + 1):
        next_index = current_index + step
        if next_index >= len(lines):
            break
        if next_index in line_indexes_with_dates:
            break
        next_line = lines[next_index]
        if _is_greeting_line(next_line):
            continue
        if any(keyword in next_line for keyword in TASK_ACTION_KEYWORDS + TASK_OBJECT_KEYWORDS + EVENT_HINT_KEYWORDS + PREP_HINT_KEYWORDS):
            collected.append(next_index)
        elif step == 1:
            collected.append(next_index)

    ordered = []
    seen = set()
    for index in collected:
        if index in seen:
            continue
        seen.add(index)
        ordered.append(lines[index])
    return ordered



def _build_event_title(base_line, support_text):
    context_keyword = _extract_context_keyword(support_text)
    if context_keyword:
        return context_keyword[:200]
    cleaned = _strip_date_prefix(base_line)
    if cleaned:
        return cleaned[:200]
    return "메시지에서 찾은 일정"



def _build_deadline_title(support_text):
    context_keyword = _extract_context_keyword(support_text)
    object_keyword = _extract_object_keyword(support_text)
    action_keyword = _extract_action_keyword(support_text)
    parts = []
    if context_keyword:
        parts.append(context_keyword)
    if object_keyword:
        parts.append(object_keyword)
    if action_keyword and action_keyword not in {"부탁", "안내"}:
        parts.append(action_keyword)
    parts.append("마감")
    title = " ".join(dict.fromkeys([part for part in parts if part]))
    return (title or "메시지에서 찾은 마감")[:200]



def _build_prep_title(support_text):
    context_keyword = _extract_context_keyword(support_text)
    object_keyword = _extract_object_keyword(support_text)
    if context_keyword and object_keyword:
        return f"{context_keyword} {object_keyword} 준비"[:200]
    if context_keyword:
        return f"{context_keyword} 준비"[:200]
    if object_keyword:
        return f"{object_keyword} 준비"[:200]
    return "메시지에서 찾은 준비 일정"



def _build_candidate_title(kind, line, support_lines):
    support_text = "\n".join(support_lines)
    if kind == KIND_DEADLINE:
        return _build_deadline_title(support_text)
    if kind == KIND_PREP:
        return _build_prep_title(support_text)
    return _build_event_title(line, support_text)



def _build_candidate_summary(kind, support_lines, title):
    normalized_title = (title or "").strip()
    chosen_lines = []
    for line in support_lines:
        if _is_greeting_line(line):
            continue
        cleaned = _strip_date_prefix(line)
        if not cleaned or cleaned == normalized_title:
            continue
        if kind == KIND_DEADLINE:
            if any(keyword in cleaned for keyword in TASK_ACTION_KEYWORDS + TASK_OBJECT_KEYWORDS):
                chosen_lines.append(cleaned)
        elif kind == KIND_PREP:
            if any(keyword in cleaned for keyword in PREP_HINT_KEYWORDS + TASK_OBJECT_KEYWORDS):
                chosen_lines.append(cleaned)
        else:
            if cleaned not in chosen_lines:
                chosen_lines.append(cleaned)
        if len(chosen_lines) >= 2:
            break

    if not chosen_lines:
        fallback_lines = []
        for line in support_lines:
            cleaned = _strip_date_prefix(line)
            if cleaned and cleaned != normalized_title:
                fallback_lines.append(cleaned)
            if len(fallback_lines) >= 2:
                break
        chosen_lines = fallback_lines

    return "\n".join(dict.fromkeys(chosen_lines))[:5000]



def _candidate_badge_text(kind):
    if kind == KIND_DEADLINE:
        return "마감"
    if kind == KIND_PREP:
        return "준비"
    return "행사"



def _candidate_color(kind):
    if kind == KIND_DEADLINE:
        return "rose"
    if kind == KIND_PREP:
        return "amber"
    return "indigo"



def _build_candidate_datetimes(mention, parsed_time, local_tz):
    if parsed_time:
        start_naive = datetime.combine(mention["value"], parsed_time["start"])
        end_naive = datetime.combine(mention["value"], parsed_time["end"])
        return (
            timezone.make_aware(start_naive, local_tz),
            timezone.make_aware(end_naive, local_tz),
            bool(parsed_time["is_all_day"]),
        )
    start_naive = datetime.combine(mention["value"], time(hour=0, minute=0))
    end_naive = datetime.combine(mention["value"], time(hour=23, minute=59))
    return timezone.make_aware(start_naive, local_tz), timezone.make_aware(end_naive, local_tz), True



def _build_raw_candidates(lines, date_mentions, *, now, has_files=False):
    local_tz = timezone.get_current_timezone()
    candidates = []
    for mention in date_mentions:
        base_line = lines[mention["line_index"]]
        support_lines = _collect_support_lines(lines, date_mentions, mention)
        support_text = "\n".join(support_lines)
        parsed_time = _extract_time(support_text)
        kind = _infer_candidate_kind(base_line, support_text)
        title = _build_candidate_title(kind, base_line, support_lines)
        summary = _build_candidate_summary(kind, support_lines, title)
        start_at, end_at, is_all_day = _build_candidate_datetimes(mention, parsed_time, local_tz)
        confidence_score = _calculate_confidence(
            has_title=bool(title),
            has_date=True,
            has_time=bool(parsed_time),
            has_summary=bool(summary),
            relative_date=bool(mention["is_relative"]),
            inferred_date=bool(mention["year_inferred"] or mention["month_inferred"]),
            ambiguous_time=bool(parsed_time and parsed_time["ambiguous"]),
        )
        needs_check = bool(
            mention["is_relative"]
            or mention["year_inferred"]
            or mention["month_inferred"]
            or (parsed_time and parsed_time["ambiguous"])
            or float(confidence_score) < 65
        )
        candidates.append(
            {
                "kind": kind,
                "badge_text": _candidate_badge_text(kind),
                "title": title,
                "summary": summary,
                "start_time": start_at,
                "end_time": end_at,
                "is_all_day": is_all_day,
                "confidence_score": confidence_score,
                "confidence_label": _confidence_label(confidence_score),
                "is_recommended": float(confidence_score) >= 55,
                "needs_check": needs_check,
                "already_saved": False,
                "evidence_text": "\n".join(dict.fromkeys(support_lines))[:1000],
                "evidence_payload": {
                    "date": mention["evidence"],
                    "time": parsed_time["evidence"] if parsed_time else "",
                    "support_lines": support_lines,
                    "relative_date": bool(mention["is_relative"]),
                    "year_inferred": bool(mention["year_inferred"]),
                    "month_inferred": bool(mention["month_inferred"]),
                    "line_index": mention["line_index"],
                },
                "color": _candidate_color(kind),
            }
        )

    return _dedupe_candidates(candidates)



def _dedupe_candidates(candidates):
    deduped = []
    seen = set()
    for candidate in candidates:
        start_time = candidate.get("start_time")
        dedupe_key = (
            candidate.get("kind"),
            start_time.date().isoformat() if start_time else "",
            candidate.get("title"),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(candidate)
    deduped.sort(key=lambda item: (item.get("start_time") or timezone.now(), item.get("kind") != KIND_DEADLINE, item.get("title") or ""))
    return deduped



def _should_refine_candidates_with_llm(lines, candidates):
    if len(candidates) >= 2:
        return True
    if lines and _is_greeting_line(lines[0]):
        return True
    return any(candidate.get("needs_check") for candidate in candidates)



def _apply_llm_refinements(candidates, refined_candidates):
    if not isinstance(refined_candidates, list):
        return candidates, False
    applied = False
    updated = []
    for index, candidate in enumerate(candidates):
        refined = refined_candidates[index] if index < len(refined_candidates) and isinstance(refined_candidates[index], dict) else {}
        merged = dict(candidate)
        refined_kind = str(refined.get("kind") or "").strip().lower()
        if refined_kind in {KIND_EVENT, KIND_DEADLINE, KIND_PREP}:
            merged["kind"] = refined_kind
            merged["badge_text"] = _candidate_badge_text(refined_kind)
            merged["color"] = _candidate_color(refined_kind)
            applied = True
        for key in ("title", "summary", "evidence_text"):
            value = str(refined.get(key) or "").strip()
            if value:
                merged[key] = value[:5000] if key == "summary" else value[:1000]
                applied = True
        if "is_recommended" in refined:
            merged["is_recommended"] = bool(refined.get("is_recommended"))
            applied = True
        updated.append(merged)
    return updated, applied



def _legacy_predicted_item_type_from_candidates(candidates):
    if not candidates:
        return "ignore"
    first_kind = candidates[0].get("kind")
    if first_kind == KIND_EVENT:
        return "event"
    return "task"



def _legacy_primary_candidate(candidates):
    if not candidates:
        return None
    recommended = [candidate for candidate in candidates if candidate.get("is_recommended")]
    return (recommended or candidates)[0]



def parse_message_capture_draft(raw_text, *, now=None, has_files=False, llm_refiner=None):
    now = now or timezone.now()
    now_date = timezone.localtime(now).date()
    normalized_text, lines = _normalize_text(raw_text)
    materials = _extract_materials(lines)
    location = _extract_location(normalized_text, lines)
    audience = _extract_audience(normalized_text)
    category = _extract_category(normalized_text)
    recurrence_hint = _extract_recurrence_hint(normalized_text)
    extracted_priority, priority_evidence = _extract_priority(normalized_text)

    date_mentions = _infer_line_date_mentions(lines, now_date)
    warnings = []
    llm_used = False

    candidates = _build_raw_candidates(lines, date_mentions, now=now, has_files=has_files)

    if candidates and llm_refiner and _should_refine_candidates_with_llm(lines, candidates):
        try:
            refined_candidates = llm_refiner(
                normalized_text=normalized_text,
                lines=lines,
                candidates=candidates,
            )
            candidates, llm_used = _apply_llm_refinements(candidates, refined_candidates)
        except Exception:
            llm_used = False

    if not candidates:
        parse_status = "failed" if not has_files else "needs_review"
        warnings.append("메시지에서 저장할 날짜를 찾지 못했어요. 날짜가 들어간 문장을 붙여 넣어 주세요.")
        confidence_score = Decimal("20.00")
        confidence_label = "low"
        predicted_item_type = "ignore"
        summary_text = "저장할 날짜를 찾지 못했어요."
        return {
            "normalized_text": normalized_text,
            "parse_status": parse_status,
            "confidence_score": confidence_score,
            "confidence_label": confidence_label,
            "predicted_item_type": predicted_item_type,
            "summary_text": summary_text,
            "candidates": [],
            "extracted_title": "메시지에서 만든 일정",
            "extracted_start_time": None,
            "extracted_end_time": None,
            "extracted_is_all_day": False,
            "extracted_priority": extracted_priority,
            "extracted_todo_summary": "",
            "deadline_only": False,
            "location": location,
            "materials": materials,
            "audience": audience,
            "category": category,
            "recurrence_hint": recurrence_hint,
            "task_due_at": None,
            "task_has_time": False,
            "task_note": "",
            "warnings": warnings,
            "llm_used": llm_used,
            "evidence": {
                "date": "",
                "time": "",
                "priority": priority_evidence,
            },
        }

    for candidate in candidates:
        if candidate.get("evidence_payload", {}).get("relative_date"):
            warnings.append("상대 날짜 표현이 있어 한 번만 확인해 주세요.")
            break
    for candidate in candidates:
        evidence_payload = candidate.get("evidence_payload") or {}
        if evidence_payload.get("year_inferred") or evidence_payload.get("month_inferred"):
            warnings.append("연도나 월이 없어서 추정한 날짜가 있어요. 저장 전 한 번만 확인해 주세요.")
            break
    if any(candidate.get("needs_check") for candidate in candidates):
        warnings.append("자동으로 읽은 일정을 한 번만 확인해 주세요.")
    if recurrence_hint:
        warnings.append("반복 일정 표현이 있어 반복 여부를 확인해 주세요.")
    warnings = list(dict.fromkeys(warnings))

    top_candidates = candidates[:5]
    if len(candidates) > 5:
        top_candidates = candidates
    primary_candidate = _legacy_primary_candidate(candidates)
    predicted_item_type = _legacy_predicted_item_type_from_candidates(candidates)
    confidence_score = max((candidate.get("confidence_score") or Decimal("0.00") for candidate in candidates), default=Decimal("0.00"))
    confidence_label = _confidence_label(confidence_score)
    parse_status = "parsed" if not any(candidate.get("needs_check") for candidate in candidates) else "needs_review"
    summary_text = f"찾은 일정 {len(candidates)}개"

    task_due_at = None
    task_has_time = False
    if primary_candidate and primary_candidate.get("kind") in {KIND_DEADLINE, KIND_PREP}:
        task_due_at = primary_candidate.get("end_time")
        task_has_time = not primary_candidate.get("is_all_day")

    return {
        "normalized_text": normalized_text,
        "parse_status": parse_status,
        "confidence_score": confidence_score,
        "confidence_label": confidence_label,
        "predicted_item_type": predicted_item_type,
        "summary_text": summary_text,
        "candidates": top_candidates,
        "extracted_title": (primary_candidate or {}).get("title") or "메시지에서 만든 일정",
        "extracted_start_time": (primary_candidate or {}).get("start_time"),
        "extracted_end_time": (primary_candidate or {}).get("end_time"),
        "extracted_is_all_day": bool((primary_candidate or {}).get("is_all_day")),
        "extracted_priority": extracted_priority,
        "extracted_todo_summary": (primary_candidate or {}).get("summary") or "",
        "deadline_only": bool(primary_candidate and primary_candidate.get("kind") == KIND_DEADLINE),
        "location": location,
        "materials": materials,
        "audience": audience,
        "category": category,
        "recurrence_hint": recurrence_hint,
        "task_due_at": task_due_at,
        "task_has_time": task_has_time,
        "task_note": (primary_candidate or {}).get("summary") or "",
        "warnings": warnings,
        "llm_used": llm_used,
        "evidence": {
            "date": (primary_candidate or {}).get("evidence_payload", {}).get("date", ""),
            "time": (primary_candidate or {}).get("evidence_payload", {}).get("time", ""),
            "priority": priority_evidence,
        },
    }
