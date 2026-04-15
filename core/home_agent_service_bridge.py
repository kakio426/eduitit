from __future__ import annotations

import json
import re
import secrets
from datetime import datetime

from django.contrib.messages.storage.fallback import FallbackStorage
from django.test.client import RequestFactory
from django.utils import timezone
from django.utils.dateparse import parse_datetime


class HomeAgentServiceUnavailable(Exception):
    """Raised when a native service cannot satisfy the home agent request."""


class HomeAgentExecutionError(Exception):
    """Raised when a native service cannot complete the requested write action."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


_PERIOD_RE = re.compile(r"(\d{1,2})\s*교시")
_CLASSROOM_GRADE_CLASS_RE = re.compile(r"(?P<grade>\d{1,2})\s*학년\s*(?P<class_no>\d{1,2})\s*반")
_ALERT_RE = re.compile(r"alert\(['\"](?P<message>.+?)['\"]\)")


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
    if normalized_mode == "pdf":
        return _generate_pdf_preview(mode_spec=mode_spec)
    return None


def execute_service_action(
    *,
    request,
    mode_key: str,
    mode_spec: dict,
    data: dict | None = None,
) -> dict:
    if request is None or not getattr(getattr(request, "user", None), "is_authenticated", False):
        raise HomeAgentExecutionError("로그인이 필요합니다.", status_code=401)

    normalized_mode = str(mode_key or "").strip().lower()
    payload = data if isinstance(data, dict) else {}

    if normalized_mode == "schedule":
        return _execute_schedule_action(
            request=request,
            mode_spec=mode_spec,
            data=payload,
        )
    if normalized_mode == "reservation":
        return _execute_reservation_action(
            request=request,
            mode_spec=mode_spec,
            data=payload,
        )
    if normalized_mode == "teacher-law":
        return _execute_teacher_law_action(
            request=request,
            mode_spec=mode_spec,
            data=payload,
        )
    raise HomeAgentExecutionError("이 모드는 홈에서 바로 저장할 수 없습니다.", status_code=400)


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
    parsed = _parse_schedule_candidates(text)
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

    execution = _build_schedule_execution(candidates)
    if execution:
        execution["warnings"] = [
            _compact_text(warning)
            for warning in parsed.get("warnings") or []
            if _compact_text(warning)
        ][:3]

    return _build_service_response(
        provider="classcalendar",
        preview=_build_preview(
            mode_spec=mode_spec,
            title="캘린더 확인",
            items=items or ["일정으로 읽을 날짜를 찾지 못했습니다."],
        ),
        execution=execution,
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
        execution=_build_teacher_law_execution(result=result, question=text),
    )


def _generate_pdf_preview(*, mode_spec: dict) -> dict:
    return _build_service_response(
        provider="hwpxchat",
        preview=_build_preview(
            mode_spec=mode_spec,
            title="문서 업로드",
            items=["문서는 PDF 화면에서 올립니다."],
        ),
    )


def _generate_reservation_preview(*, request, mode_spec: dict, text: str, selected_date_label: str) -> dict:
    from reservations.models import SchoolConfig, SpecialRoom
    from reservations.utils import list_user_accessible_schools

    schools = [
        entry
        for entry in list_user_accessible_schools(request.user)
        if entry.get("can_edit")
    ]
    if not schools:
        return _build_service_response(
            provider="reservations",
            preview=_build_preview(
                mode_spec=mode_spec,
                title="예약판 없음",
                items=["편집할 수 있는 특별실 예약판이 없습니다."],
            ),
        )

    school_map = {entry["school"].id: entry for entry in schools}
    rooms = list(
        SpecialRoom.objects.filter(school_id__in=school_map.keys())
        .only("id", "name", "school_id")
        .order_by("school_id", "name", "id")
    )
    parsed = _parse_schedule_candidates(text, use_llm_refiner=False)
    primary_candidate = _pick_primary_candidate(parsed.get("candidates") or [])
    matched_room = _match_room(text, rooms)
    selected_school_entry = school_map.get(matched_room.school_id) if matched_room else schools[0]

    school_options = []
    for entry in schools:
        school = entry["school"]
        config, _ = SchoolConfig.objects.get_or_create(school=school)
        school_rooms = [
            {
                "id": str(room.id),
                "name": room.name,
            }
            for room in rooms
            if room.school_id == school.id
        ]
        school_options.append(
            {
                "slug": school.slug,
                "name": school.name,
                "reservation_url": entry.get("reservation_url", ""),
                "rooms": school_rooms,
                "periods": [
                    {
                        "id": slot["id"],
                        "label": slot["label"],
                        "display_label": slot["display_label"],
                    }
                    for slot in config.get_period_slots()
                ],
            }
        )

    selected_school_option = _find_school_option(school_options, selected_school_entry["school"].slug) or school_options[0]
    matched_period = _match_reservation_period(
        text=text,
        candidate=primary_candidate,
        school_option=selected_school_option,
    )
    matched_room_id = ""
    if matched_room and selected_school_option and matched_room.school_id == selected_school_entry["school"].id:
        matched_room_id = str(matched_room.id)
    default_party = _extract_classroom_party(request)
    owner_type = "class" if default_party["grade"] and default_party["class_no"] else "custom"

    draft = {
        "school_slug": selected_school_option.get("slug", ""),
        "room_id": matched_room_id,
        "date": _format_reservation_date_iso(primary_candidate),
        "period": str(matched_period["id"]) if matched_period else "",
        "owner_type": owner_type,
        "grade": str(default_party["grade"]) if default_party["grade"] else "",
        "class_no": str(default_party["class_no"]) if default_party["class_no"] else "",
        "target_label": "",
        "name": _default_reservation_name(request),
        "memo": "",
        "edit_code": _generate_edit_code(),
        "override_grade_lock": False,
    }

    room_option = _find_room_option(selected_school_option, draft["room_id"])
    items = [
        f"예약판 · {selected_school_option.get('name') or '확인 필요'}",
        f"날짜 · {_format_reservation_date(primary_candidate, selected_date_label)}",
        f"시간 · {matched_period['display_label'] if matched_period else _format_reservation_time(text, primary_candidate)}",
        f"장소 · {room_option['name'] if room_option else '선택 필요'}",
    ]
    if not room_option and selected_school_option.get("rooms"):
        room_names = ", ".join(room["name"] for room in selected_school_option["rooms"][:3])
        items.append(f"가능 장소 · {room_names}")

    warnings = []
    if not draft["date"]:
        warnings.append("날짜를 확인해 주세요.")
    if not draft["period"]:
        warnings.append("교시를 선택해 주세요.")
    if not draft["room_id"]:
        warnings.append("장소를 선택해 주세요.")

    return _build_service_response(
        provider="reservations",
        preview=_build_preview(
            mode_spec=mode_spec,
            title="예약 확인",
            items=items,
        ),
        execution={
            "kind": "reservation",
            "title": "예약 확인",
            "submit_label": "예약 넣기",
            "draft": draft,
            "school_options": school_options,
            "warnings": warnings,
        },
    )


def _execute_schedule_action(*, request, mode_spec: dict, data: dict) -> dict:
    from classcalendar.views import api_create_event

    title = _compact_text(data.get("title"))
    start_time = _compact_text(data.get("start_time"))
    end_time = _compact_text(data.get("end_time"))
    note = str(data.get("note") or "").strip()
    color = _compact_text(data.get("color")) or "indigo"
    calendar_owner_id = _compact_text(data.get("calendar_owner_id"))
    is_all_day = _is_truthy(data.get("is_all_day"))

    if not title:
        raise HomeAgentExecutionError("일정 이름을 입력해 주세요.")
    if not start_time or not end_time:
        raise HomeAgentExecutionError("시작과 종료 시간을 확인해 주세요.")

    form_data = {
        "title": title,
        "note": note,
        "calendar_owner_id": calendar_owner_id,
        "start_time": start_time,
        "end_time": end_time,
        "color": color,
    }
    if is_all_day:
        form_data["is_all_day"] = "1"

    subrequest = _build_subrequest(
        request,
        path="/classcalendar/api/events/create/",
        data=form_data,
    )
    response = api_create_event(subrequest)
    payload = _decode_json_response(response)
    if response.status_code >= 400:
        raise HomeAgentExecutionError(
            _extract_first_error_text(payload.get("errors"))
            or _compact_text(payload.get("detail"))
            or _compact_text(payload.get("error"))
            or "캘린더에 저장하지 못했습니다.",
            status_code=response.status_code,
        )

    saved_label = _format_saved_schedule_result(
        start_time=start_time,
        end_time=end_time,
        is_all_day=is_all_day,
        title=title,
    )
    items = [saved_label]
    if note:
        items.append(note)

    return _build_service_response(
        provider="classcalendar",
        preview=_build_preview(
            mode_spec=mode_spec,
            title="캘린더에 넣었습니다.",
            items=items,
        ),
        message="캘린더에 저장했습니다.",
    )


def _execute_reservation_action(*, request, mode_spec: dict, data: dict) -> dict:
    from reservations.models import Reservation, School, SchoolConfig, SpecialRoom
    from reservations.views import create_reservation

    school_slug = _compact_text(data.get("school_slug"))
    room_id = _compact_text(data.get("room_id"))
    date_value = _compact_text(data.get("date"))
    period_value = _compact_text(data.get("period"))
    owner_type = _compact_text(data.get("owner_type")) or "custom"
    grade = _compact_text(data.get("grade"))
    class_no = _compact_text(data.get("class_no"))
    target_label = _compact_text(data.get("target_label"))
    name = _compact_text(data.get("name"))
    memo = str(data.get("memo") or "").strip()
    edit_code = _compact_text(data.get("edit_code"))
    override_grade_lock = _is_truthy(data.get("override_grade_lock"))

    if not school_slug:
        raise HomeAgentExecutionError("예약판을 선택해 주세요.")

    form_data = {
        "room_id": room_id,
        "date": date_value,
        "period": period_value,
        "name": name,
        "memo": memo,
        "edit_code": edit_code,
    }
    if owner_type == "class":
        form_data["grade"] = grade
        form_data["class_no"] = class_no
        form_data["target_label"] = ""
    else:
        form_data["grade"] = ""
        form_data["class_no"] = ""
        form_data["target_label"] = target_label
    if override_grade_lock:
        form_data["override_grade_lock"] = "1"

    subrequest = _build_subrequest(
        request,
        path=f"/reservations/{school_slug}/create/",
        data=form_data,
        attach_messages=True,
    )
    response = create_reservation(subrequest, school_slug)
    if response.status_code >= 400 or response.headers.get("HX-Refresh") != "true":
        status_code = response.status_code if response.status_code >= 400 else 400
        raise HomeAgentExecutionError(
            _extract_response_message(response) or "예약하지 못했습니다.",
            status_code=status_code,
        )

    school = School.objects.filter(slug=school_slug).first()
    room = SpecialRoom.objects.filter(id=room_id).first()
    reservation = Reservation.objects.filter(
        room_id=room_id,
        date=date_value,
        period=period_value,
    ).select_related("room", "room__school").first()
    if reservation and school is None:
        school = reservation.room.school
    if reservation and room is None:
        room = reservation.room

    config = None
    if school is not None:
        config, _ = SchoolConfig.objects.get_or_create(school=school)
    period_label = _format_period_label_from_config(config, period_value)
    party_label = _format_reservation_party(owner_type, grade, class_no, target_label, name)
    date_label = _format_reservation_iso_label(date_value)

    items = [
        " · ".join(
            part
            for part in (
                getattr(school, "name", "") or "",
                date_label,
                period_label,
                getattr(room, "name", "") or "",
            )
            if part
        ) or "예약이 완료되었습니다.",
        party_label,
    ]
    if memo:
        items.append(memo)

    return _build_service_response(
        provider="reservations",
        preview=_build_preview(
            mode_spec=mode_spec,
            title="예약을 넣었습니다.",
            items=items,
        ),
        message="예약이 완료되었습니다.",
    )


def _execute_teacher_law_action(*, request, mode_spec: dict, data: dict) -> dict:
    from teacher_law.views import ask_question_api

    question = _compact_text(data.get("question"))
    incident_type = _compact_text(data.get("incident_type"))
    legal_goal = _compact_text(data.get("legal_goal"))
    scene = _compact_text(data.get("scene"))
    counterpart = _compact_text(data.get("counterpart"))

    if not question:
        raise HomeAgentExecutionError("질문을 입력해 주세요.")

    payload = {
        "question": question,
        "incident_type": incident_type,
        "legal_goal": legal_goal,
        "scene": scene,
        "counterpart": counterpart,
    }
    subrequest = _build_json_subrequest(
        request,
        path="/teacher-law/api/ask/",
        data=payload,
    )
    response = ask_question_api(subrequest)
    response_payload = _decode_json_response(response)
    if response.status_code >= 400:
        raise HomeAgentExecutionError(
            _compact_text(response_payload.get("message"))
            or _extract_first_error_text(response_payload.get("field_errors"))
            or "법률 대화에 남기지 못했습니다.",
            status_code=response.status_code,
        )

    assistant_message = response_payload.get("assistant_message") if isinstance(response_payload.get("assistant_message"), dict) else {}
    items = []
    summary = _compact_text(assistant_message.get("summary"))
    if summary:
        items.append(summary)
    items.extend(
        _compact_text(item)
        for item in assistant_message.get("action_items") or []
        if _compact_text(item)
    )
    if not items:
        body = _compact_text(assistant_message.get("body"))
        if body:
            items.append(body)

    return _build_service_response(
        provider="teacher_law",
        preview=_build_preview(
            mode_spec=mode_spec,
            title="법률 대화에 남겼습니다.",
            items=items or ["법률 대화에 저장했습니다."],
        ),
        message="법률 서비스 대화에 저장했습니다.",
    )


def _parse_schedule_candidates(text: str, *, use_llm_refiner: bool = True) -> dict:
    from classcalendar.message_capture import parse_message_capture_draft
    from classcalendar.message_capture_llm import refine_message_capture_candidates

    return parse_message_capture_draft(
        text,
        now=timezone.now(),
        has_files=False,
        llm_refiner=refine_message_capture_candidates if use_llm_refiner else None,
    )


def _build_schedule_execution(candidates: list[dict]) -> dict | None:
    choices = []
    for index, candidate in enumerate(candidates[:5]):
        draft = _build_schedule_draft(candidate)
        if not draft["title"] or not draft["start_time"] or not draft["end_time"]:
            continue
        choices.append(
            {
                "id": str(index),
                "label": _format_schedule_candidate(candidate),
                "values": draft,
            }
        )
    if not choices:
        return None

    return {
        "kind": "schedule",
        "title": "일정 확인",
        "submit_label": "캘린더에 넣기",
        "draft": choices[0]["values"],
        "choices": choices,
        "warnings": [],
    }


def _build_teacher_law_execution(*, result: dict, question: str) -> dict:
    from teacher_law.services.query_normalizer import (
        COUNTERPART_OPTIONS,
        INCIDENT_OPTIONS,
        LEGAL_GOAL_OPTIONS,
        SCENE_OPTIONS,
    )

    payload = result.get("payload") or {}
    profile = result.get("profile") or {}
    warnings = [
        _compact_text(item)
        for item in payload.get("clarify_questions") or []
        if _compact_text(item)
    ][:3]
    if not warnings and payload.get("clarify_needed") and _compact_text(payload.get("clarify_reason")):
        warnings.append(_compact_text(payload.get("clarify_reason")))

    return {
        "kind": "teacher-law",
        "title": "법률 대화 저장",
        "submit_label": "법률 대화에 남기기",
        "draft": {
            "question": _compact_text(question),
            "incident_type": _compact_text(profile.get("incident_type")),
            "legal_goal": _compact_text(profile.get("legal_goal")),
            "scene": _compact_text(profile.get("scene_value")),
            "counterpart": _compact_text(profile.get("counterpart")),
        },
        "incident_options": [
            {
                "value": option["value"],
                "label": option["label"],
                "requires": option.get("requires", ""),
            }
            for option in INCIDENT_OPTIONS
        ],
        "goal_options": [
            {"value": option["value"], "label": option["label"]}
            for option in LEGAL_GOAL_OPTIONS
        ],
        "scene_options": [
            {"value": option["value"], "label": option["label"]}
            for option in SCENE_OPTIONS
        ],
        "counterpart_options": [
            {"value": option["value"], "label": option["label"]}
            for option in COUNTERPART_OPTIONS
        ],
        "warnings": warnings,
    }


def _build_schedule_draft(candidate: dict) -> dict:
    start_time = candidate.get("start_time")
    end_time = candidate.get("end_time")
    title = _compact_text(candidate.get("title") or candidate.get("summary") or "새 일정")
    note_parts = [
        _compact_text(candidate.get("summary")),
        _compact_text(candidate.get("evidence_text")),
    ]
    seen = set()
    note = []
    for part in note_parts:
        if part and part not in seen and part != title:
            seen.add(part)
            note.append(part)
    return {
        "title": title,
        "note": " ".join(note).strip(),
        "start_time": _format_datetime_local_value(start_time),
        "end_time": _format_datetime_local_value(end_time),
        "is_all_day": bool(candidate.get("is_all_day")),
        "color": "indigo",
        "calendar_owner_id": "",
    }


def _build_subrequest(request, *, path: str, data: dict, attach_messages: bool = False) -> object:
    subrequest = RequestFactory().post(path, data=data)
    subrequest.user = request.user
    subrequest.session = request.session
    subrequest.COOKIES = dict(getattr(request, "COOKIES", {}) or {})
    subrequest._dont_enforce_csrf_checks = True
    if attach_messages and hasattr(subrequest, "session"):
        setattr(subrequest, "_messages", FallbackStorage(subrequest))
    for meta_key in ("REMOTE_ADDR", "HTTP_X_FORWARDED_FOR", "HTTP_USER_AGENT"):
        if request.META.get(meta_key):
            subrequest.META[meta_key] = request.META.get(meta_key)
    return subrequest


def _build_json_subrequest(request, *, path: str, data: dict) -> object:
    subrequest = RequestFactory().post(
        path,
        data=json.dumps(data),
        content_type="application/json",
    )
    subrequest.user = request.user
    subrequest.session = request.session
    subrequest.COOKIES = dict(getattr(request, "COOKIES", {}) or {})
    subrequest._dont_enforce_csrf_checks = True
    for meta_key in ("REMOTE_ADDR", "HTTP_X_FORWARDED_FOR", "HTTP_USER_AGENT"):
        if request.META.get(meta_key):
            subrequest.META[meta_key] = request.META.get(meta_key)
    return subrequest


def _build_service_response(*, provider: str, preview: dict, execution: dict | None = None, message: str = "") -> dict:
    response = {
        "preview": preview,
        "provider": provider,
        "model": "service-native",
    }
    if execution:
        response["execution"] = execution
    if message:
        response["message"] = message
    return response


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


def _decode_json_response(response) -> dict:
    try:
        return json.loads((response.content or b"").decode("utf-8") or "{}")
    except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _extract_first_error_text(value) -> str:
    if isinstance(value, list):
        for item in value:
            message = _extract_first_error_text(item)
            if message:
                return message
        return ""
    if isinstance(value, dict):
        if _compact_text(value.get("message")):
            return _compact_text(value.get("message"))
        for nested in value.values():
            message = _extract_first_error_text(nested)
            if message:
                return message
    if isinstance(value, str):
        return _compact_text(value)
    return ""


def _extract_response_message(response) -> str:
    raw_text = ""
    try:
        raw_text = (response.content or b"").decode("utf-8").strip()
    except (AttributeError, UnicodeDecodeError):
        raw_text = ""
    if not raw_text:
        return ""
    match = _ALERT_RE.search(raw_text)
    if match:
        return _compact_text(match.group("message"))
    cleaned = re.sub(r"<[^>]+>", " ", raw_text)
    return _compact_text(cleaned)


def _compact_text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", " ").strip()


def _pick_primary_candidate(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    recommended = [candidate for candidate in candidates if candidate.get("is_recommended")]
    return (recommended or candidates)[0]


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


def _format_datetime_local_value(value) -> str:
    if not value:
        return ""
    return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M")


def _format_saved_schedule_result(*, start_time: str, end_time: str, is_all_day: bool, title: str) -> str:
    parsed_start = parse_datetime(start_time)
    parsed_end = parse_datetime(end_time)
    if parsed_start is None:
        return title
    if timezone.is_naive(parsed_start):
        parsed_start = timezone.make_aware(parsed_start, timezone.get_current_timezone())
    if parsed_end is not None and timezone.is_naive(parsed_end):
        parsed_end = timezone.make_aware(parsed_end, timezone.get_current_timezone())
    date_label = _format_datetime_label(parsed_start, parsed_end, is_all_day=is_all_day)
    return f"{date_label} · {title}"


def _format_reservation_date(candidate: dict | None, selected_date_label: str) -> str:
    if candidate and candidate.get("start_time"):
        local_start = timezone.localtime(candidate["start_time"])
        return f"{local_start.month}월 {local_start.day}일"
    return _compact_text(selected_date_label) or "확인 필요"


def _format_reservation_date_iso(candidate: dict | None) -> str:
    if candidate and candidate.get("start_time"):
        return timezone.localtime(candidate["start_time"]).date().isoformat()
    return ""


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


def _match_reservation_period(*, text: str, candidate: dict | None, school_option: dict | None) -> dict | None:
    periods = list((school_option or {}).get("periods") or [])
    if not periods:
        return None

    match = _PERIOD_RE.search(str(text or ""))
    if match:
        target_id = int(match.group(1))
        for period in periods:
            if period.get("id") == target_id:
                return period

    if not candidate or not candidate.get("start_time"):
        return None

    local_start = timezone.localtime(candidate["start_time"]).time()
    local_end = timezone.localtime(candidate.get("end_time") or candidate["start_time"]).time()
    for period in periods:
        start_time, end_time = _parse_period_time_range(period.get("display_label") or period.get("label") or "")
        if start_time is None or end_time is None:
            continue
        if start_time <= local_start <= end_time and local_end <= end_time:
            return period
    return None


def _parse_period_time_range(value: str):
    parts = re.findall(r"(\d{2}:\d{2})", str(value or ""))
    if len(parts) < 2:
        return None, None
    try:
        start_time = datetime.strptime(parts[0], "%H:%M").time()
        end_time = datetime.strptime(parts[1], "%H:%M").time()
    except ValueError:
        return None, None
    return start_time, end_time


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


def _find_school_option(school_options: list[dict], school_slug: str) -> dict | None:
    normalized_slug = _compact_text(school_slug)
    for option in school_options or []:
        if _compact_text(option.get("slug")) == normalized_slug:
            return option
    return None


def _find_room_option(school_option: dict | None, room_id: str) -> dict | None:
    normalized_room_id = str(room_id or "").strip()
    for room in (school_option or {}).get("rooms") or []:
        if str(room.get("id")) == normalized_room_id:
            return room
    return None


def _extract_classroom_party(request) -> dict:
    from core.active_classroom import get_active_classroom_for_request

    classroom = get_active_classroom_for_request(request) if hasattr(request, "session") else None
    classroom_name = getattr(classroom, "name", "") or ""
    match = _CLASSROOM_GRADE_CLASS_RE.search(classroom_name)
    if not match:
        return {"grade": 0, "class_no": 0}
    return {
        "grade": int(match.group("grade")),
        "class_no": int(match.group("class_no")),
    }


def _default_reservation_name(request) -> str:
    full_name = _compact_text(request.user.get_full_name()) if hasattr(request.user, "get_full_name") else ""
    if full_name:
        return full_name
    return _compact_text(getattr(request.user, "username", ""))


def _generate_edit_code() -> str:
    return str(1000 + secrets.randbelow(9000))


def _format_period_label_from_config(config, period_value) -> str:
    normalized = _compact_text(period_value)
    if not normalized:
        return "교시 확인"
    try:
        period_int = int(normalized)
    except (TypeError, ValueError):
        return f"{normalized}교시"
    for slot in config.get_period_slots() if config is not None else []:
        if slot.get("id") == period_int:
            return slot.get("display_label") or slot.get("label") or f"{period_int}교시"
    return f"{period_int}교시"


def _format_reservation_party(owner_type: str, grade: str, class_no: str, target_label: str, name: str) -> str:
    if owner_type == "class":
        grade_text = _compact_text(grade)
        class_text = _compact_text(class_no)
        if grade_text and class_text:
            return f"대상 · {grade_text}학년 {class_text}반 {name}".strip()
    label = _compact_text(target_label)
    if label:
        return f"대상 · {label} {name}".strip()
    return f"예약자 · {name}".strip()


def _format_reservation_iso_label(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return "날짜 확인"
    return f"{parsed.month}월 {parsed.day}일"


def _is_truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())
