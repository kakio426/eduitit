from __future__ import annotations

import re

from django.test.client import RequestFactory
from django.utils import timezone


class HomeAgentServiceUnavailable(Exception):
    """Raised when a native service cannot satisfy the home agent request."""


_PERIOD_RE = re.compile(r"(\d{1,2})\s*교시")


def generate_service_preview(
    *,
    request,
    mode_key: str,
    mode_spec: dict,
    text: str,
    selected_date_label: str = "",
    context: dict | None = None,
) -> dict | None:
    if request is None or not getattr(getattr(request, "user", None), "is_authenticated", False):
        return None

    normalized_mode = str(mode_key or "").strip().lower()
    if normalized_mode == "notice":
        return _generate_notice_preview(
            request=request,
            mode_spec=mode_spec,
            text=text,
        )
    if normalized_mode == "schedule":
        return _generate_schedule_preview(
            mode_spec=mode_spec,
            text=text,
        )
    if normalized_mode == "teacher-law":
        return _generate_teacher_law_preview(
            mode_spec=mode_spec,
            text=text,
        )
    if normalized_mode == "reservation":
        return _generate_reservation_preview(
            request=request,
            mode_spec=mode_spec,
            text=text,
            selected_date_label=selected_date_label,
        )
    return None


def _generate_notice_preview(*, request, mode_spec: dict, text: str) -> dict:
    from noticegen.views import _generate_notice_payload

    subrequest = _build_subrequest(
        request,
        path="/noticegen/generate-mini/",
        data={
            "keywords": text,
            "target": "",
            "topic": "",
            "length_style": "",
        },
    )
    status_code, payload = _generate_notice_payload(subrequest)
    result_text = _compact_text(payload.get("result_text"))
    service_message = (
        result_text
        or _compact_text(payload.get("error_message"))
        or _compact_text(payload.get("limit_message"))
        or _compact_text(payload.get("info_message"))
    )
    if not service_message:
        raise HomeAgentServiceUnavailable("알림장 서비스를 아직 불러오지 못했습니다.")

    title = "알림장 결과" if result_text else "알림장 안내"
    if status_code >= 500 and not result_text:
        raise HomeAgentServiceUnavailable(service_message)
    return _build_service_response(
        provider="noticegen",
        preview=_build_preview(
            mode_spec=mode_spec,
            title=title,
            items=[service_message],
        ),
    )


def _generate_schedule_preview(*, mode_spec: dict, text: str) -> dict:
    from classcalendar.message_capture import parse_message_capture_draft
    from classcalendar.message_capture_llm import refine_message_capture_candidates

    parsed = parse_message_capture_draft(
        text,
        now=timezone.now(),
        has_files=False,
        llm_refiner=refine_message_capture_candidates,
    )
    candidates = parsed.get("candidates") or []
    items = [_format_schedule_candidate(candidate) for candidate in candidates]
    items = [item for item in items if item]
    if not items:
        items = [
            _compact_text(warning)
            for warning in parsed.get("warnings") or []
            if _compact_text(warning)
        ]
    if not items and _compact_text(parsed.get("summary_text")):
        items = [_compact_text(parsed.get("summary_text"))]

    return _build_service_response(
        provider="classcalendar",
        preview=_build_preview(
            mode_spec=mode_spec,
            title="캘린더 후보",
            items=items or ["일정으로 읽을 날짜를 찾지 못했습니다."],
        ),
    )


def _generate_teacher_law_preview(*, mode_spec: dict, text: str) -> dict:
    from teacher_law.services import answer_legal_question
    from teacher_law.services.chat import TeacherLawDisabledError
    from teacher_law.services.law_api import LawApiConfigError
    from teacher_law.services.llm_client import LlmClientError

    try:
        result = answer_legal_question(question=text)
    except (TeacherLawDisabledError, LawApiConfigError, LlmClientError) as exc:
        raise HomeAgentServiceUnavailable(str(exc)) from exc

    payload = result.get("payload") or {}
    items = []
    summary = _compact_text(payload.get("summary"))
    if summary:
        items.append(summary)
    items.extend(
        _compact_text(question)
        for question in payload.get("clarify_questions") or []
        if _compact_text(question)
    )
    items.extend(
        _compact_text(action)
        for action in payload.get("action_items") or []
        if _compact_text(action)
    )
    if not items and _compact_text(payload.get("reasoning_summary")):
        items.append(_compact_text(payload.get("reasoning_summary")))

    representative_case = payload.get("representative_case") if isinstance(payload.get("representative_case"), dict) else None
    representative_title = _compact_text((representative_case or {}).get("title") or (representative_case or {}).get("law_name"))
    if representative_title and len(items) < 4:
        items.append(f"대표 판례 · {representative_title}")

    return _build_service_response(
        provider="teacher_law",
        preview=_build_preview(
            mode_spec=mode_spec,
            title="법률 답변" if not payload.get("clarify_needed") else "추가 확인",
            items=items or ["질문과 바로 맞는 답변을 아직 만들지 못했습니다."],
        ),
    )


def _generate_reservation_preview(*, request, mode_spec: dict, text: str, selected_date_label: str) -> dict:
    from classcalendar.message_capture import parse_message_capture_draft
    from reservations.models import SpecialRoom
    from reservations.utils import list_user_accessible_schools

    schools = list_user_accessible_schools(request.user)
    if not schools:
        return _build_service_response(
            provider="reservations",
            preview=_build_preview(
                mode_spec=mode_spec,
                title="예약판 없음",
                items=["열 수 있는 특별실 예약판이 없습니다."],
            ),
        )

    school_map = {entry["school"].id: entry for entry in schools}
    rooms = list(
        SpecialRoom.objects.filter(school_id__in=school_map.keys())
        .only("name", "school_id")
        .order_by("name", "id")
    )
    parsed = parse_message_capture_draft(text, now=timezone.now(), has_files=False)
    primary_candidate = (parsed.get("candidates") or [None])[0]
    matched_room = _match_room(text, rooms)
    matched_school_entry = school_map.get(matched_room.school_id) if matched_room else (schools[0] if len(schools) == 1 else None)

    items = [
        f"예약판 · {matched_school_entry['school'].name}" if matched_school_entry else "예약판 · 선택 필요",
        f"날짜 · {_format_reservation_date(primary_candidate, selected_date_label)}",
        f"시간 · {_format_reservation_time(text, primary_candidate)}",
        f"장소 · {matched_room.name}" if matched_room else "장소 · 확인 필요",
    ]

    if not matched_room and rooms:
        room_names = ", ".join(room.name for room in rooms[:3])
        items.append(f"가능 장소 · {room_names}")

    return _build_service_response(
        provider="reservations",
        preview=_build_preview(
            mode_spec=mode_spec,
            title="예약 값 확인",
            items=items,
        ),
    )


def _build_subrequest(request, *, path: str, data: dict) -> object:
    subrequest = RequestFactory().post(path, data=data)
    subrequest.user = request.user
    subrequest.session = request.session
    subrequest.COOKIES = dict(getattr(request, "COOKIES", {}) or {})
    for meta_key in ("REMOTE_ADDR", "HTTP_X_FORWARDED_FOR", "HTTP_USER_AGENT"):
        if request.META.get(meta_key):
            subrequest.META[meta_key] = request.META.get(meta_key)
    return subrequest


def _build_service_response(*, provider: str, preview: dict) -> dict:
    return {
        "preview": preview,
        "provider": provider,
        "model": "service-native",
    }


def _build_preview(*, mode_spec: dict, title: str, items: list[str]) -> dict:
    cleaned_items = [
        _compact_text(item)
        for item in items
        if _compact_text(item)
    ][:4]
    return {
        "badge": mode_spec.get("badge") or "",
        "title": title,
        "summary": cleaned_items[0] if cleaned_items else "",
        "sections": [
            {
                "title": "결과",
                "items": cleaned_items[:4] or [mode_spec.get("default_title") or ""],
            }
        ],
        "note": "",
    }


def _compact_text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ").strip()


def _format_schedule_candidate(candidate: dict) -> str:
    start_time = candidate.get("start_time")
    end_time = candidate.get("end_time")
    title = _compact_text(candidate.get("title"))
    summary = _compact_text(candidate.get("summary"))
    if not start_time:
        return title or summary

    start_label = _format_datetime_label(start_time, end_time, is_all_day=bool(candidate.get("is_all_day")))
    parts = [start_label]
    if title:
        parts.append(title)
    if summary and summary not in parts:
        parts.append(summary)
    return " · ".join(part for part in parts if part)


def _format_datetime_label(start_time, end_time, *, is_all_day: bool) -> str:
    local_start = timezone.localtime(start_time)
    date_label = f"{local_start.month}월 {local_start.day}일"
    if is_all_day:
        return f"{date_label} · 하루 종일"
    time_label = local_start.strftime("%H:%M")
    if end_time:
        local_end = timezone.localtime(end_time)
        if local_end.date() == local_start.date():
            time_label = f"{time_label}-{local_end.strftime('%H:%M')}"
    return f"{date_label} · {time_label}"


def _format_reservation_date(candidate: dict | None, selected_date_label: str) -> str:
    if candidate and candidate.get("start_time"):
        local_start = timezone.localtime(candidate["start_time"])
        return f"{local_start.month}월 {local_start.day}일"
    return _compact_text(selected_date_label) or "확인 필요"


def _format_reservation_time(text: str, candidate: dict | None) -> str:
    match = _PERIOD_RE.search(str(text or ""))
    if match:
        return f"{match.group(1)}교시"
    if candidate and candidate.get("start_time"):
        return _format_datetime_label(
            candidate["start_time"],
            candidate.get("end_time"),
            is_all_day=bool(candidate.get("is_all_day")),
        ).split(" · ", 1)[-1]
    return "확인 필요"


def _match_room(text: str, rooms) -> object | None:
    normalized_text = _normalize_match_text(text)
    if not normalized_text:
        return None

    matched = []
    for room in rooms:
        room_name = getattr(room, "name", "") or ""
        normalized_room_name = _normalize_match_text(room_name)
        if normalized_room_name and normalized_room_name in normalized_text:
            matched.append((len(normalized_room_name), room))
    if not matched:
        return None
    matched.sort(key=lambda item: item[0], reverse=True)
    return matched[0][1]


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())
