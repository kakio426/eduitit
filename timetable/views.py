import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from products.models import Product
from reservations.models import ReservationCollaborator, School, SpecialRoom

from .forms import TimetableTeacherForm, WorkspaceBatchCreateForm, WorkspaceCreateForm
from .models import (
    DEFAULT_DAY_KEYS,
    TimetableClassroom,
    TimetableClassEditLink,
    TimetableClassInputStatus,
    TimetableDateOverride,
    TimetableRoomPolicy,
    TimetableSchoolProfile,
    TimetableShareLink,
    TimetableSharePortal,
    TimetableSharedEvent,
    TimetableSlotAssignment,
    TimetableSnapshot,
    TimetableTeacher,
    TimetableWorkspace,
)
from .services import (
    assignments_to_sheet_data,
    apply_meeting_selections,
    build_classroom_date_rows,
    build_default_period_labels,
    build_date_override_block_reason,
    build_effective_event_payloads,
    build_effective_date_assignments,
    build_serialized_date_overrides,
    build_week_label,
    build_event_slot_map,
    build_meeting_matrix,
    build_teacher_stat_rows,
    build_workspace_sheet_data,
    day_key_for_date,
    generate_timetable_schedule,
    get_workspace_date_overrides,
    get_effective_shared_events,
    legacy_generated_result_to_sheet_data,
    normalize_sheet_data,
    parse_display_text,
    publish_to_reservations,
    serialize_validation_result,
    validate_timetable_workbook,
    validate_workspace_assignments,
)
from .services.normalizer import build_display_text


SERVICE_TITLE = "우리학교 시간표"


def _apply_workspace_cache_headers(response):
    response["Cache-Control"] = "private, no-cache, must-revalidate"
    response["Pragma"] = "no-cache"
    return response


def _apply_sensitive_cache_headers(response):
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def _get_service():
    service = Product.objects.filter(launch_route_name="timetable:main").first()
    if service:
        return service
    return Product.objects.filter(title=SERVICE_TITLE).first()


def _json_error(message, *, status=400):
    return JsonResponse({"ok": False, "message": message}, status=status)


def _json_validation_error(message, *, validation, teacher_stats, status=409):
    return JsonResponse(
        {
            "ok": False,
            "message": message,
            "validation": serialize_validation_result(validation),
            "teacher_stats": _serialize_teacher_stats(teacher_stats),
        },
        status=status,
    )


def _parse_json_request(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None


def _request_payload(request):
    if "application/json" in (request.content_type or ""):
        payload = _parse_json_request(request)
        return payload if payload is not None else None
    return request.POST


def _get_editable_schools(request):
    if not request.user.is_authenticated:
        return []

    collaborator_school_ids = list(
        ReservationCollaborator.objects.filter(
            collaborator=request.user,
            can_edit=True,
        ).values_list("school_id", flat=True)
    )
    return list(
        School.objects.filter(Q(owner=request.user) | Q(id__in=collaborator_school_ids))
        .select_related("owner")
        .distinct()
        .order_by("name")
    )


def _get_school_choices(request):
    schools = _get_editable_schools(request)
    return [(school.slug, school.name) for school in schools], {school.slug: school for school in schools}


def _get_accessible_workspaces(request):
    schools = _get_editable_schools(request)
    school_ids = [school.id for school in schools]
    if not school_ids:
        return TimetableWorkspace.objects.none()
    return (
        TimetableWorkspace.objects.filter(school_id__in=school_ids)
        .select_related("school", "published_snapshot")
        .order_by("school__name", "school_year", "term", "grade")
    )


def _get_or_create_timetable_profile(school):
    profile, _created = TimetableSchoolProfile.objects.get_or_create(
        school=school,
        defaults={
            "school_stage": TimetableSchoolProfile.SchoolStage.ELEMENTARY,
            "grade_start": 1,
            "grade_end": 6,
        },
    )
    return profile


def _extract_class_counts(request, grade_range):
    counts = {}
    for grade in grade_range:
        raw_value = (request.POST.get(f"class_count_{grade}") or "").strip()
        if not raw_value:
            raise ValidationError(f"{grade}학년 반 수를 입력해 주세요.")
        try:
            class_count = int(raw_value)
        except (TypeError, ValueError):
            raise ValidationError(f"{grade}학년 반 수를 숫자로 입력해 주세요.")
        if class_count < 1 or class_count > 30:
            raise ValidationError(f"{grade}학년 반 수는 1~30 사이로 입력해 주세요.")
        counts[grade] = class_count
    return counts


def _get_workspace_class_input_status_map(workspace):
    return {
        item.classroom_id: item
        for item in workspace.class_input_statuses.select_related("classroom").all()
    }


def _get_workspace_class_edit_link_map(workspace):
    return {
        item.classroom_id: item
        for item in workspace.class_edit_links.select_related("classroom").all()
    }


def _ensure_classroom_input_assets(workspace, *, issued_by=None):
    classrooms = _workspace_classrooms(workspace)
    status_map = _get_workspace_class_input_status_map(workspace)
    link_map = _get_workspace_class_edit_link_map(workspace)
    missing_statuses = []
    missing_links = []
    for classroom in classrooms:
        if classroom.id not in status_map:
            missing_statuses.append(
                TimetableClassInputStatus(
                    workspace=workspace,
                    classroom=classroom,
                )
            )
        if classroom.id not in link_map:
            missing_links.append(
                TimetableClassEditLink(
                    workspace=workspace,
                    classroom=classroom,
                    issued_by=issued_by,
                )
            )
    if missing_statuses:
        TimetableClassInputStatus.objects.bulk_create(missing_statuses)
    if missing_links:
        TimetableClassEditLink.objects.bulk_create(missing_links)
    return classrooms


def _format_datetime_label(value):
    if not value:
        return ""
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


def _default_class_link_expiry(workspace):
    if workspace.term_end_date:
        return timezone.make_aware(datetime.combine(workspace.term_end_date, datetime.max.time().replace(microsecond=0)))
    return timezone.now() + timedelta(days=120)


def _serialize_classroom_input_rows(request, workspace):
    _ensure_classroom_input_assets(workspace, issued_by=request.user if request.user.is_authenticated else None)
    status_map = _get_workspace_class_input_status_map(workspace)
    link_map = _get_workspace_class_edit_link_map(workspace)
    rows = []
    for classroom in _workspace_classrooms(workspace):
        status = status_map.get(classroom.id)
        link = link_map.get(classroom.id)
        link_url = ""
        if link and link.is_active and not link.is_expired:
            link_url = request.build_absolute_uri(reverse("timetable:class_edit", args=[link.token]))
        rows.append(
            {
                "classroom_id": classroom.id,
                "classroom_label": classroom.label,
                "status": status.status if status else TimetableClassInputStatus.Status.NOT_STARTED,
                "status_label": status.get_status_display() if status else TimetableClassInputStatus.Status.NOT_STARTED.label,
                "editor_name": status.editor_name if status else "",
                "last_saved_at_label": _format_datetime_label(status.last_saved_at) if status else "",
                "submitted_at_label": _format_datetime_label(status.submitted_at) if status else "",
                "reviewed_at_label": _format_datetime_label(status.reviewed_at) if status else "",
                "review_note": status.review_note if status else "",
                "link_id": link.id if link else None,
                "link_url": link_url,
                "link_active": bool(link and link.is_active and not link.is_expired),
                "link_expires_at_label": _format_datetime_label(link.expires_at) if link and link.expires_at else "",
                "issue_url": reverse("timetable:api_issue_class_link", args=[workspace.id]),
                "revoke_url": reverse("timetable:api_revoke_class_link", args=[workspace.id, link.id if link else 0]),
                "review_url": reverse("timetable:api_review_class_status", args=[workspace.id, classroom.id]),
            }
        )
    return rows


def _parse_iso_date(raw_value):
    if not raw_value:
        return None
    try:
        return datetime.strptime(str(raw_value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _cell_value(value):
    if value in (None, ""):
        return None
    return {"v": value, "m": value, "ct": {"fa": "General", "t": "g"}}


def _build_classroom_sheet_from_entries(workspace, classroom, entries):
    days = list(workspace.day_keys)
    periods = list(workspace.period_labels)
    data = [[None for _ in range(len(days) + 1)] for _ in range(len(periods) + 1)]
    data[0][0] = _cell_value("교시")
    for day_index, day_key in enumerate(days, start=1):
        data[0][day_index] = _cell_value(day_key)
    for period_no, period_label in enumerate(periods, start=1):
        data[period_no][0] = _cell_value(period_label)
    for item in entries:
        day_index = days.index(item["day_key"]) + 1
        data[item["period_no"]][day_index] = _cell_value(item["text"])
    return {
        "name": classroom.label,
        "id": f"classroom-{classroom.id}",
        "order": classroom.class_no,
        "row": len(periods) + 1,
        "column": len(days) + 1,
        "defaultRowHeight": 32,
        "defaultColWidth": 140,
        "showGridLines": 1,
        "data": data,
        "config": {},
    }


def _build_classroom_weekly_rows(workspace, classroom):
    assignment_lookup = {
        (item.day_key, item.period_no): item
        for item in workspace.assignments.select_related("teacher", "special_room").filter(classroom=classroom)
    }
    rows = []
    for period_no, period_label in enumerate(workspace.period_labels, start=1):
        cells = []
        for day_key in workspace.day_keys:
            assignment = assignment_lookup.get((day_key, period_no))
            cells.append(
                {
                    "day_key": day_key,
                    "period_no": period_no,
                    "text": assignment.display_text if assignment else "",
                }
            )
        rows.append({"period_no": period_no, "period_label": period_label, "cells": cells})
    return rows


def _update_class_input_status(workspace, classroom, *, editor_name, submitted=False, reviewed=False, review_note=""):
    status, _created = TimetableClassInputStatus.objects.get_or_create(workspace=workspace, classroom=classroom)
    now = timezone.now()
    if editor_name:
        status.editor_name = editor_name
    status.last_saved_at = now
    if reviewed:
        status.status = TimetableClassInputStatus.Status.REVIEWED
        status.reviewed_at = now
        status.review_note = review_note
    elif submitted:
        status.status = TimetableClassInputStatus.Status.SUBMITTED
        status.submitted_at = now
    else:
        status.status = TimetableClassInputStatus.Status.EDITING
    status.save()
    return status


def _persist_class_weekly_entries(workspace, classroom, entries, *, editor_name, submitted=False):
    teachers = _workspace_teachers(workspace)
    rooms = _workspace_rooms(workspace)
    room_policies = _ensure_room_policies(workspace)
    sheet = _build_classroom_sheet_from_entries(workspace, classroom, entries)
    assignment_dicts, issues = normalize_sheet_data(workspace, [sheet], [classroom], teachers, rooms)
    new_assignments = [TimetableSlotAssignment(source=TimetableSlotAssignment.Source.MANUAL, **item) for item in assignment_dicts]
    other_assignments = list(
        workspace.assignments.exclude(classroom=classroom).select_related("classroom", "teacher", "special_room")
    )
    preview_assignments = other_assignments + new_assignments
    effective_events = _build_effective_events(workspace)
    validation = validate_workspace_assignments(
        workspace,
        preview_assignments,
        room_policies,
        issues=issues,
        effective_events=effective_events,
    )

    with transaction.atomic():
        workspace.assignments.filter(classroom=classroom).delete()
        if new_assignments:
            TimetableSlotAssignment.objects.bulk_create(new_assignments)
        workspace.sheet_data = assignments_to_sheet_data(workspace)
        workspace.status = TimetableWorkspace.Status.DRAFT
        workspace.save(update_fields=["sheet_data", "status", "updated_at"])
        _update_class_input_status(workspace, classroom, editor_name=editor_name, submitted=submitted)

    saved_assignments = list(
        workspace.assignments.select_related("classroom", "teacher", "special_room").order_by(
            "classroom__class_no",
            "day_key",
            "period_no",
            "id",
        )
    )
    return {
        "validation": validation,
        "teacher_stats": build_teacher_stat_rows(teachers, saved_assignments),
        "redirect_url": reverse("timetable:class_edit", args=[_get_workspace_class_edit_link_map(workspace)[classroom.id].token]),
    }


def _persist_class_date_override_entries(workspace, classroom, target_date, entries, *, editor_name, submitted=False):
    teachers = _workspace_teachers(workspace)
    teacher_by_name = {teacher.name: teacher for teacher in teachers}
    rooms = _workspace_rooms(workspace)
    room_by_name = {room.name: room for room in rooms}
    room_policies = _ensure_room_policies(workspace)
    weekly_assignments = list(
        workspace.assignments.select_related("classroom", "teacher", "special_room").all()
    )
    existing_same_day = {
        item.period_no: item
        for item in get_workspace_date_overrides(workspace, classroom=classroom, target_date=target_date)
    }
    other_same_day_overrides = [
        item
        for item in get_workspace_date_overrides(workspace, target_date=target_date)
        if item.classroom_id != classroom.id
    ]
    weekly_lookup = {
        (item.classroom_id, item.period_no): item
        for item in weekly_assignments
        if item.day_key == day_key_for_date(target_date)
    }
    issues = []
    new_overrides = []
    for entry in entries:
        period_no = int(entry["period_no"])
        raw_text = str(entry.get("text") or "").strip()
        if not raw_text:
            continue
        parsed = parse_display_text(raw_text)
        teacher = teacher_by_name.get(parsed["teacher_name"]) if parsed["teacher_name"] else None
        special_room = room_by_name.get(parsed["room_name"]) if parsed["room_name"] else None
        if parsed["teacher_name"] and not teacher:
            issues.append(
                {
                    "kind": "teacher",
                    "message": f"{classroom.label} {target_date} {period_no}교시에 입력한 교사 '{parsed['teacher_name']}'를 찾지 못했습니다.",
                    "cell_key": f"{classroom.id}:{day_key_for_date(target_date)}:{period_no}",
                }
            )
        if parsed["room_name"] and not special_room:
            issues.append(
                {
                    "kind": "room",
                    "message": f"{classroom.label} {target_date} {period_no}교시에 입력한 특별실 '{parsed['room_name']}'를 찾지 못했습니다.",
                    "cell_key": f"{classroom.id}:{day_key_for_date(target_date)}:{period_no}",
                }
            )
        base_assignment = weekly_lookup.get((classroom.id, period_no))
        blocked_reason = build_date_override_block_reason(base_assignment)
        if blocked_reason and period_no not in existing_same_day:
            issues.append(
                {
                    "kind": "override",
                    "message": f"{classroom.label} {target_date} {period_no}교시는 {blocked_reason}",
                    "cell_key": f"{classroom.id}:{day_key_for_date(target_date)}:{period_no}",
                }
            )
        for message in parsed["issues"]:
            issues.append(
                {
                    "kind": "format",
                    "message": f"{classroom.label} {target_date} {period_no}교시: {message}",
                    "cell_key": f"{classroom.id}:{day_key_for_date(target_date)}:{period_no}",
                }
            )
        new_overrides.append(
            TimetableDateOverride(
                workspace=workspace,
                classroom=classroom,
                date=target_date,
                period_no=period_no,
                subject_name=parsed["subject_name"],
                teacher=teacher,
                special_room=special_room,
                source=TimetableDateOverride.Source.TEACHER_LINK,
                display_text=parsed["display_text"] or raw_text,
                note="",
            )
        )

    effective_events = _build_effective_events(workspace)
    effective_assignments = build_effective_date_assignments(
        workspace,
        target_date,
        weekly_assignments,
        other_same_day_overrides + new_overrides,
    )["assignments"]
    validation = validate_workspace_assignments(
        workspace,
        effective_assignments,
        room_policies,
        issues=issues,
        effective_events=effective_events,
    )

    with transaction.atomic():
        workspace.date_overrides.filter(classroom=classroom, date=target_date).delete()
        if new_overrides:
            TimetableDateOverride.objects.bulk_create(new_overrides)
        workspace.status = TimetableWorkspace.Status.DRAFT
        workspace.save(update_fields=["status", "updated_at"])
        _update_class_input_status(workspace, classroom, editor_name=editor_name, submitted=submitted)

    link = _get_workspace_class_edit_link_map(workspace)[classroom.id]
    return {
        "validation": validation,
        "teacher_stats": build_teacher_stat_rows(teachers, list(workspace.assignments.select_related("teacher", "classroom"))),
        "redirect_url": reverse("timetable:class_edit", args=[link.token]) + f"?mode=daily&date={target_date.isoformat()}",
    }


def _get_public_class_edit_link_or_404(token):
    link = get_object_or_404(
        TimetableClassEditLink.objects.select_related("workspace", "workspace__school", "classroom"),
        token=token,
        is_active=True,
    )
    if link.is_expired:
        raise Http404
    return link


def _resolve_class_editor_name(workspace, classroom, payload):
    current_status = TimetableClassInputStatus.objects.filter(workspace=workspace, classroom=classroom).first()
    editor_name = str((payload or {}).get("editor_name") or (current_status.editor_name if current_status else "") or "").strip()
    if not editor_name:
        raise ValidationError("처음 저장하기 전에 입력자 이름을 적어 주세요.")
    return editor_name


def _normalize_weekly_entries(workspace, payload):
    entries = payload.get("entries") or []
    if not isinstance(entries, list):
        raise ValidationError("시간표 칸 정보를 다시 확인해 주세요.")
    normalized = []
    for item in entries:
        day_key = str(item.get("day_key") or "").strip()
        try:
            period_no = int(item.get("period_no"))
        except (TypeError, ValueError):
            raise ValidationError("시간표 칸 정보를 다시 확인해 주세요.")
        if day_key not in workspace.day_keys or period_no < 1 or period_no > len(workspace.period_labels):
            raise ValidationError("시간표 칸 정보를 다시 확인해 주세요.")
        normalized.append(
            {
                "day_key": day_key,
                "period_no": period_no,
                "text": str(item.get("text") or "").strip(),
            }
        )
    return normalized


def _normalize_date_override_entries(workspace, payload):
    entries = payload.get("entries") or []
    if not isinstance(entries, list):
        raise ValidationError("날짜별 일정 칸 정보를 다시 확인해 주세요.")
    normalized = []
    for item in entries:
        try:
            period_no = int(item.get("period_no"))
        except (TypeError, ValueError):
            raise ValidationError("날짜별 일정 칸 정보를 다시 확인해 주세요.")
        if period_no < 1 or period_no > len(workspace.period_labels):
            raise ValidationError("날짜별 일정 칸 정보를 다시 확인해 주세요.")
        normalized.append({"period_no": period_no, "text": str(item.get("text") or "").strip()})
    return normalized


def _get_editable_workspace_or_404(request, workspace_id):
    if not request.user.is_authenticated:
        raise Http404
    workspace = get_object_or_404(
        TimetableWorkspace.objects.select_related("school", "published_snapshot"),
        pk=workspace_id,
    )
    school = workspace.school
    if school.owner_id == request.user.id:
        return workspace
    relation = ReservationCollaborator.objects.filter(
        school=school,
        collaborator=request.user,
        can_edit=True,
    ).first()
    if relation:
        return workspace
    raise Http404


def _workspace_classrooms(workspace):
    return list(
        TimetableClassroom.objects.filter(
            school=workspace.school,
            school_year=workspace.school_year,
            grade=workspace.grade,
            is_active=True,
        ).order_by("class_no", "id")
    )


def _workspace_teachers(workspace):
    return list(
        TimetableTeacher.objects.filter(school=workspace.school, is_active=True)
        .order_by("teacher_type", "name", "id")
    )


def _workspace_rooms(workspace):
    return list(SpecialRoom.objects.filter(school=workspace.school).order_by("name", "id"))


def _ensure_room_policies(workspace):
    rooms = _workspace_rooms(workspace)
    existing_room_ids = set(
        TimetableRoomPolicy.objects.filter(workspace=workspace).values_list("special_room_id", flat=True)
    )
    missing = [
        TimetableRoomPolicy(workspace=workspace, special_room=room, capacity_per_slot=1)
        for room in rooms
        if room.id not in existing_room_ids
    ]
    if missing:
        TimetableRoomPolicy.objects.bulk_create(missing)
    return list(
        TimetableRoomPolicy.objects.filter(workspace=workspace)
        .select_related("special_room")
        .order_by("special_room__name", "id")
    )


def _build_runtime_assignments(workspace, sheet_data, *, source=TimetableSlotAssignment.Source.MANUAL):
    classrooms = _workspace_classrooms(workspace)
    teachers = _workspace_teachers(workspace)
    rooms = _workspace_rooms(workspace)
    assignment_dicts, issues = normalize_sheet_data(workspace, sheet_data, classrooms, teachers, rooms)
    assignments = []
    for item in assignment_dicts:
        item = dict(item)
        item["source"] = source
        assignments.append(TimetableSlotAssignment(**item))
    return classrooms, teachers, rooms, assignments, issues


def _build_workspace_state(workspace):
    classrooms = _workspace_classrooms(workspace)
    teachers = _workspace_teachers(workspace)
    rooms = _workspace_rooms(workspace)
    room_policies = _ensure_room_policies(workspace)
    _ensure_classroom_input_assets(workspace, issued_by=workspace.updated_by or workspace.created_by)
    assignments = list(
        workspace.assignments.select_related("classroom", "teacher", "special_room").order_by(
            "classroom__class_no",
            "day_key",
            "period_no",
            "id",
        )
    )
    date_overrides = get_workspace_date_overrides(workspace)
    if not workspace.sheet_data:
        workspace.sheet_data = build_workspace_sheet_data(workspace, classrooms, assignments)
        workspace.save(update_fields=["sheet_data", "updated_at"])

    effective_events = _build_effective_events(workspace)
    validation = validate_workspace_assignments(
        workspace,
        assignments,
        room_policies,
        effective_events=effective_events,
    )
    teacher_stats = build_teacher_stat_rows(teachers, assignments)
    return {
        "classrooms": classrooms,
        "teachers": teachers,
        "rooms": rooms,
        "room_policies": room_policies,
        "assignments": assignments,
        "date_overrides": date_overrides,
        "effective_events": effective_events,
        "validation": validation,
        "teacher_stats": teacher_stats,
    }


def _persist_workspace_sheet_data(workspace, sheet_data, *, user, source=TimetableSlotAssignment.Source.MANUAL):
    classrooms, teachers, rooms, runtime_assignments, issues = _build_runtime_assignments(
        workspace,
        sheet_data,
        source=source,
    )
    room_policies = _ensure_room_policies(workspace)
    effective_events = _build_effective_events(workspace)
    validation = validate_workspace_assignments(
        workspace,
        runtime_assignments,
        room_policies,
        issues=issues,
        effective_events=effective_events,
    )

    with transaction.atomic():
        workspace.assignments.all().delete()
        TimetableSlotAssignment.objects.bulk_create(runtime_assignments)
        workspace.sheet_data = sheet_data
        workspace.updated_by = user
        workspace.status = TimetableWorkspace.Status.DRAFT
        workspace.save(update_fields=["sheet_data", "updated_by", "status", "updated_at"])

    saved_assignments = list(
        workspace.assignments.select_related("classroom", "teacher", "special_room").order_by(
            "classroom__class_no",
            "day_key",
            "period_no",
            "id",
        )
    )
    teacher_stats = build_teacher_stat_rows(teachers, saved_assignments)
    return {
        "classrooms": classrooms,
        "teachers": teachers,
        "rooms": rooms,
        "room_policies": room_policies,
        "assignments": saved_assignments,
        "effective_events": effective_events,
        "validation": validation,
        "teacher_stats": teacher_stats,
    }


def _serialize_teacher_stats(rows):
    return [dict(row) for row in rows]


def _serialize_effective_events(events):
    return [dict(item) for item in events]


def _build_effective_events(workspace):
    return build_effective_event_payloads(workspace, get_effective_shared_events(workspace))


def _has_blocking_conflicts(validation):
    summary = (validation or {}).get("summary") or {}
    return bool(summary.get("conflict_count") or (validation or {}).get("conflicts"))


def _build_snapshot_summary(state):
    validation = serialize_validation_result(state["validation"])
    return {
        "validation": validation,
        "teacher_stats": _serialize_teacher_stats(state["teacher_stats"]),
    }


def _create_snapshot(workspace, *, created_by, name):
    state = _build_workspace_state(workspace)
    return TimetableSnapshot.objects.create(
        workspace=workspace,
        name=name,
        sheet_data=workspace.sheet_data,
        events_json=state["effective_events"],
        date_overrides_json=build_serialized_date_overrides(workspace, state["date_overrides"]),
        summary_json=_build_snapshot_summary(state),
        created_by=created_by,
    )


def _create_share_links(snapshot):
    workspace = snapshot.workspace
    assignments = list(workspace.assignments.select_related("classroom", "teacher"))
    class_ids = [classroom.id for classroom in _workspace_classrooms(workspace)]
    teacher_ids = sorted({assignment.teacher_id for assignment in assignments if assignment.teacher_id})

    links = []
    for classroom_id in class_ids:
        links.append(
            TimetableShareLink.objects.create(
                snapshot=snapshot,
                audience_type=TimetableShareLink.AudienceType.CLASSROOM,
                classroom_id=classroom_id,
            )
        )
    for teacher_id in teacher_ids:
        links.append(
            TimetableShareLink.objects.create(
                snapshot=snapshot,
                audience_type=TimetableShareLink.AudienceType.TEACHER,
                teacher_id=teacher_id,
            )
        )
    return links


def _create_share_portal(snapshot):
    return TimetableSharePortal.objects.create(snapshot=snapshot)


def _serialize_share_portal(request, portal):
    if not portal:
        return None
    return {
        "token": portal.token,
        "label": "교사용 모아보기",
        "url": request.build_absolute_uri(reverse("timetable:share_portal", args=[portal.token])),
    }


def _share_link_label(link):
    if link.classroom_id and link.classroom:
        return link.classroom.label
    if link.teacher_id and link.teacher:
        return link.teacher.name
    return ""


def _serialize_share_links(request, links):
    serialized = []
    for link in links:
        audience_label = _share_link_label(link)
        if not audience_label:
            continue
        serialized.append(
            {
                "token": link.token,
                "audience_type": link.audience_type,
                "audience_label": audience_label,
                "url": request.build_absolute_uri(reverse("timetable:share_view", args=[link.token])),
            }
        )
    serialized.sort(key=lambda item: (item["audience_type"], item["audience_label"]))
    return serialized


def _group_serialized_share_links(links):
    class_links = []
    teacher_links = []
    for link in links:
        if link.get("audience_type") == TimetableShareLink.AudienceType.CLASSROOM:
            class_links.append(link)
        else:
            teacher_links.append(link)
    return class_links, teacher_links


def _serialize_snapshot_summary(request, workspace, snapshot, *, is_published):
    return {
        "id": snapshot.id,
        "name": snapshot.name,
        "created_at": snapshot.created_at.isoformat(),
        "created_at_label": timezone.localtime(snapshot.created_at).strftime("%Y-%m-%d %H:%M"),
        "is_published": is_published,
        "restore_url": reverse("timetable:api_snapshot_restore", args=[workspace.id, snapshot.id]),
    }


def _build_share_portal_sections(request, portal):
    snapshot = portal.snapshot
    class_links = []
    teacher_links = []
    for link in snapshot.share_links.select_related("classroom", "teacher").order_by("audience_type", "id"):
        label = _share_link_label(link)
        if not label:
            continue
        item = {
            "label": label,
            "url": request.build_absolute_uri(reverse("timetable:share_view", args=[link.token])),
        }
        if link.audience_type == TimetableShareLink.AudienceType.CLASSROOM:
            class_links.append(item)
        else:
            teacher_links.append(item)
    return {"class_links": class_links, "teacher_links": teacher_links}


def _workspace_event_queryset(workspace):
    return TimetableSharedEvent.objects.filter(
        school=workspace.school,
        school_year=workspace.school_year,
        term=workspace.term,
        is_active=True,
    ).filter(
        Q(scope_type=TimetableSharedEvent.ScopeType.SCHOOL)
        | Q(scope_type=TimetableSharedEvent.ScopeType.GRADE, grade=workspace.grade)
    )


def _get_workspace_event_or_404(workspace, event_id):
    return get_object_or_404(_workspace_event_queryset(workspace), pk=event_id)


def _event_payload_to_instance(workspace, payload, *, user, event=None):
    scope_type = str(payload.get("scope_type") or "").strip()
    title = str(payload.get("title") or "").strip()
    day_key = str(payload.get("day_key") or "").strip()
    note = str(payload.get("note") or "").strip()
    try:
        period_start = int(payload.get("period_start"))
        period_end = int(payload.get("period_end"))
    except (TypeError, ValueError):
        raise ValidationError("시작 교시와 종료 교시를 확인해 주세요.")

    if scope_type not in {
        TimetableSharedEvent.ScopeType.SCHOOL,
        TimetableSharedEvent.ScopeType.GRADE,
    }:
        raise ValidationError("행사 범위를 다시 선택해 주세요.")
    if not title:
        raise ValidationError("행사 이름을 입력해 주세요.")
    if day_key not in workspace.day_keys:
        raise ValidationError("요일을 다시 선택해 주세요.")
    if period_start < 1 or period_end > len(workspace.period_labels):
        raise ValidationError("교시 범위를 다시 선택해 주세요.")

    instance = event or TimetableSharedEvent(
        school=workspace.school,
        school_year=workspace.school_year,
        term=workspace.term,
        created_by=user,
    )
    instance.scope_type = scope_type
    instance.grade = workspace.grade if scope_type == TimetableSharedEvent.ScopeType.GRADE else None
    instance.title = title
    instance.day_key = day_key
    instance.period_start = period_start
    instance.period_end = period_end
    instance.note = note
    instance.updated_by = user
    instance.full_clean()
    return instance


def _extract_matrix_cell(sheet, row_index, col_index):
    matrix = list((sheet or {}).get("data") or [])
    if row_index >= len(matrix):
        return ""
    row = matrix[row_index] or []
    if col_index >= len(row):
        return ""
    cell = row[col_index]
    if not cell:
        return ""
    return str(cell.get("m") or cell.get("v") or "").strip()


def _build_class_share_rows(snapshot, classroom, teacher_lookup):
    rows = []
    sheet = None
    event_slot_map = build_event_slot_map(snapshot.events_json or [])
    for candidate in snapshot.sheet_data or []:
        if (candidate or {}).get("name") == classroom.label:
            sheet = candidate
            break

    for period_no, period_label in enumerate(snapshot.workspace.period_labels, start=1):
        cells = []
        for day_index, day_key in enumerate(snapshot.workspace.day_keys, start=1):
            text = _extract_matrix_cell(sheet or {}, period_no, day_index)
            events = event_slot_map.get(f"{day_key}:{period_no}") or []
            if not text and not events:
                cells.append(None)
                continue
            parsed = parse_display_text(text) if text else parse_display_text("")
            teacher = teacher_lookup.get(parsed["teacher_name"]) if text else None
            teacher_type = teacher.teacher_type if teacher else ""
            badge = ""
            if teacher_type == TimetableTeacher.TeacherType.SPECIALIST:
                badge = "전담"
            elif teacher_type == TimetableTeacher.TeacherType.INSTRUCTOR:
                badge = "강사"
            cells.append(
                {
                    "text": text,
                    "events": events,
                    "teacher_type": teacher_type,
                    "badge": badge,
                    "is_external": teacher_type in {
                        TimetableTeacher.TeacherType.SPECIALIST,
                        TimetableTeacher.TeacherType.INSTRUCTOR,
                    },
                    "is_event_only": bool(events and not text),
                }
            )
        rows.append({"period_label": period_label, "cells": cells})
    return rows


def _build_teacher_share_rows(snapshot, teacher):
    rows = []
    event_slot_map = build_event_slot_map(snapshot.events_json or [])
    for period_no, period_label in enumerate(snapshot.workspace.period_labels, start=1):
        cells = []
        for day_index, day_key in enumerate(snapshot.workspace.day_keys, start=1):
            slot_items = []
            for sheet in snapshot.sheet_data or []:
                text = _extract_matrix_cell(sheet, period_no, day_index)
                if not text:
                    continue
                parsed = parse_display_text(text)
                if parsed["teacher_name"] != teacher.name:
                    continue
                slot_items.append(
                    {
                        "classroom_label": sheet.get("name") or "",
                        "subject_name": parsed["subject_name"] or parsed["display_text"] or text,
                        "room_name": parsed["room_name"],
                    }
                )
            cells.append(
                {
                    "events": event_slot_map.get(f"{day_key}:{period_no}") or [],
                    "assignments": slot_items,
                }
            )
        rows.append({"period_label": period_label, "cells": cells})
    return rows


def _serialize_snapshot_date_overrides(snapshot):
    workspace = snapshot.workspace
    items = []
    for item in snapshot.date_overrides_json or []:
        date_value = _parse_iso_date(item.get("date"))
        items.append(
            {
                "id": item.get("id"),
                "classroom_id": item.get("classroom_id"),
                "classroom_label": item.get("classroom_label") or "",
                "teacher_name": item.get("teacher_name") or "",
                "subject_name": item.get("subject_name") or "",
                "room_name": item.get("room_name") or "",
                "display_text": item.get("display_text") or "",
                "date": item.get("date") or "",
                "date_value": date_value,
                "date_label": item.get("date_label") or (date_value.strftime("%Y-%m-%d") if date_value else ""),
                "week_label": item.get("week_label") or (build_week_label(workspace, date_value) if date_value else ""),
                "day_key": item.get("day_key") or (day_key_for_date(date_value) if date_value else ""),
                "period_no": int(item.get("period_no") or 0),
                "note": item.get("note") or "",
                "source": item.get("source") or "",
            }
        )
    return items


def _build_share_upcoming_overrides(snapshot, *, classroom=None, teacher=None, limit=8):
    today = timezone.localdate()
    items = []
    for item in _serialize_snapshot_date_overrides(snapshot):
        if not item["date_value"] or item["date_value"] < today:
            continue
        if classroom and str(item["classroom_id"]) != str(classroom.id):
            continue
        if teacher and item["teacher_name"] != teacher.name:
            continue
        items.append(item)
    items.sort(key=lambda item: (item["date"], item["period_no"], item["classroom_label"], item["display_text"]))
    return items[:limit]


def _restore_snapshot_date_overrides(workspace, snapshot):
    teacher_lookup = {item.name: item for item in _workspace_teachers(workspace)}
    room_lookup = {item.name: item for item in _workspace_rooms(workspace)}
    classroom_lookup = {item.id: item for item in _workspace_classrooms(workspace)}
    restored = []
    for item in snapshot.date_overrides_json or []:
        classroom = classroom_lookup.get(item.get("classroom_id"))
        target_date = _parse_iso_date(item.get("date"))
        period_no = int(item.get("period_no") or 0)
        if not classroom or not target_date or period_no < 1:
            continue
        restored.append(
            TimetableDateOverride(
                workspace=workspace,
                classroom=classroom,
                date=target_date,
                period_no=period_no,
                subject_name=item.get("subject_name") or "",
                teacher=teacher_lookup.get(item.get("teacher_name") or ""),
                special_room=room_lookup.get(item.get("room_name") or ""),
                source=item.get("source") or TimetableDateOverride.Source.MANUAL,
                display_text=item.get("display_text") or "",
                note=item.get("note") or "",
            )
        )
    workspace.date_overrides.all().delete()
    if restored:
        TimetableDateOverride.objects.bulk_create(restored)


def _build_meeting_apply_preview(workspace, teacher, subject_name, room, selections, *, target_date=None):
    classrooms = _workspace_classrooms(workspace)
    teachers = _workspace_teachers(workspace)
    room_policies = _ensure_room_policies(workspace)
    classroom_map = {classroom.id: classroom for classroom in classrooms}
    current_assignments = list(
        workspace.assignments.select_related("classroom", "teacher", "special_room").order_by(
            "classroom__class_no",
            "day_key",
            "period_no",
            "id",
        )
    )
    effective_events = _build_effective_events(workspace)
    seen_keys = set()
    replacement_keys = set()
    issues = []
    normalized_selections = []
    target_day_key = day_key_for_date(target_date) if target_date else None
    date_overrides = get_workspace_date_overrides(workspace, target_date=target_date) if target_date else []
    date_context = (
        build_effective_date_assignments(workspace, target_date, current_assignments, date_overrides)
        if target_date
        else None
    )
    current_map = (
        {(item.classroom_id, item.day_key, item.period_no): item for item in date_context["assignments"]}
        if date_context
        else {(item.classroom_id, item.day_key, item.period_no): item for item in current_assignments}
    )

    for raw in selections:
        try:
            classroom_id = int(raw.get("classroom_id"))
            period_no = int(raw.get("period_no"))
        except (TypeError, ValueError):
            issues.append({"kind": "meeting", "message": "회의 반영 대상 칸 정보가 올바르지 않습니다."})
            continue
        day_key = target_day_key or str(raw.get("day_key") or "").strip()
        classroom = classroom_map.get(classroom_id)
        if not classroom or day_key not in workspace.day_keys or period_no < 1 or period_no > len(workspace.period_labels):
            issues.append(
                {
                    "kind": "meeting",
                    "message": "회의 반영 대상 칸 정보가 올바르지 않습니다.",
                    "cell_key": f"{classroom_id}:{day_key}:{period_no}",
                }
            )
            continue
        slot_key = (classroom_id, day_key, period_no)
        if slot_key in seen_keys:
            issues.append(
                {
                    "kind": "meeting",
                    "message": f"{classroom.label} {day_key} {period_no}교시가 중복 선택되었습니다.",
                    "cell_key": f"{classroom_id}:{day_key}:{period_no}",
                }
            )
            continue
        seen_keys.add(slot_key)

        if date_context:
            base_assignment = date_context["weekly_lookup"].get((classroom_id, period_no))
            override = date_context["override_lookup"].get((classroom_id, period_no))
            blocked_reason = build_date_override_block_reason(base_assignment)
            if override and override.teacher_id != teacher.id:
                issues.append(
                    {
                        "kind": "meeting",
                        "message": f"{classroom.label} {day_key} {period_no}교시는 이미 {override.display_text or override.subject_name or '다른 일정'}으로 저장되어 있습니다.",
                        "cell_key": f"{classroom_id}:{day_key}:{period_no}",
                    }
                )
                continue
            if blocked_reason and not override:
                issues.append(
                    {
                        "kind": "meeting",
                        "message": f"{classroom.label} {day_key} {period_no}교시는 {blocked_reason}",
                        "cell_key": f"{classroom_id}:{day_key}:{period_no}",
                    }
                )
                continue
        else:
            existing = current_map.get(slot_key)
            if existing and existing.teacher_id != teacher.id:
                issues.append(
                    {
                        "kind": "meeting",
                        "message": f"{classroom.label} {day_key} {period_no}교시는 이미 {existing.display_text or existing.subject_name or '다른 수업'}으로 배정되어 있습니다.",
                        "cell_key": existing.cell_key,
                    }
                )
                continue

        normalized_selections.append(
            {
                "classroom_id": classroom_id,
                "day_key": day_key,
                "period_no": period_no,
            }
        )
        replacement_keys.add(slot_key)

    if date_context and target_date:
        preview_overrides = [
            item
            for item in date_overrides
            if (item.classroom_id, target_day_key, item.period_no) not in replacement_keys
        ]
        for item in normalized_selections:
            classroom = classroom_map[item["classroom_id"]]
            preview_overrides.append(
                TimetableDateOverride(
                    workspace=workspace,
                    classroom=classroom,
                    date=target_date,
                    period_no=item["period_no"],
                    subject_name=subject_name,
                    teacher=teacher,
                    special_room=room,
                    source=TimetableDateOverride.Source.MEETING,
                    display_text=build_display_text(subject_name, teacher.name, room.name if room else ""),
                )
            )
        preview_assignments = build_effective_date_assignments(
            workspace,
            target_date,
            current_assignments,
            preview_overrides,
        )["assignments"]
    else:
        preview_assignments = [
            item
            for item in current_assignments
            if (item.classroom_id, item.day_key, item.period_no) not in replacement_keys
        ]
        for item in normalized_selections:
            classroom = classroom_map[item["classroom_id"]]
            preview_assignments.append(
                TimetableSlotAssignment(
                    workspace=workspace,
                    classroom=classroom,
                    day_key=item["day_key"],
                    period_no=item["period_no"],
                    subject_name=subject_name,
                    teacher=teacher,
                    special_room=room,
                    source=TimetableSlotAssignment.Source.MEETING,
                    display_text=build_display_text(subject_name, teacher.name, room.name if room else ""),
                )
            )

    validation = validate_workspace_assignments(
        workspace,
        preview_assignments,
        room_policies,
        issues=issues,
        effective_events=effective_events,
    )
    teacher_stats = build_teacher_stat_rows(teachers, preview_assignments)
    return {
        "normalized_selections": normalized_selections,
        "effective_events": effective_events,
        "validation": validation,
        "teacher_stats": teacher_stats,
    }


def _create_batch_workspaces(*, school, form, class_counts, user):
    created_workspaces = []
    grade_range = list(form.resolve_grade_range())
    existing_grades = set(
        TimetableWorkspace.objects.filter(
            school=school,
            school_year=form.cleaned_data["school_year"],
            term=form.cleaned_data["term"],
            grade__in=grade_range,
        ).values_list("grade", flat=True)
    )
    if existing_grades:
        grade_text = ", ".join(f"{grade}학년" for grade in sorted(existing_grades))
        raise ValidationError(f"이미 만들어진 학년이 있습니다: {grade_text}")

    with transaction.atomic():
        profile = _get_or_create_timetable_profile(school)
        profile.school_stage = form.cleaned_data["school_stage"]
        if profile.school_stage == TimetableSchoolProfile.SchoolStage.CUSTOM:
            profile.grade_start = form.cleaned_data["custom_grade_start"]
            profile.grade_end = form.cleaned_data["custom_grade_end"]
        profile.full_clean()
        profile.save()

        for grade in grade_range:
            workspace = TimetableWorkspace.objects.create(
                school=school,
                school_year=form.cleaned_data["school_year"],
                term=form.cleaned_data["term"],
                grade=grade,
                term_start_date=form.cleaned_data.get("term_start_date"),
                term_end_date=form.cleaned_data.get("term_end_date"),
                title=f"{form.cleaned_data['school_year']}학년도 {form.cleaned_data['term']} {grade}학년 시간표",
                days_json=form.cleaned_data["days_text"],
                period_labels_json=build_default_period_labels(form.cleaned_data["period_count"]),
                created_by=user,
                updated_by=user,
            )
            classrooms = []
            for class_no in range(1, class_counts[grade] + 1):
                classroom, _created = TimetableClassroom.objects.get_or_create(
                    school=school,
                    school_year=workspace.school_year,
                    grade=grade,
                    class_no=class_no,
                    defaults={"is_active": True},
                )
                classrooms.append(classroom)
            _ensure_room_policies(workspace)
            workspace.sheet_data = build_workspace_sheet_data(workspace, classrooms, [])
            workspace.save(update_fields=["sheet_data", "updated_at"])
            _ensure_classroom_input_assets(workspace, issued_by=user)
            created_workspaces.append(workspace)
    return created_workspaces


def main(request):
    service = _get_service()
    if not request.user.is_authenticated:
        response = render(
            request,
            "timetable/index.html",
            {
                "service": service,
                "requires_login": True,
                "workspace_form": None,
                "workspaces": [],
            },
        )
        return _apply_workspace_cache_headers(response)

    school_choices, school_map = _get_school_choices(request)
    workspace_form = WorkspaceBatchCreateForm(
        request.POST if request.method == "POST" and request.POST.get("action") == "create_workspace_batch" else None,
        school_choices=school_choices,
        initial={
            "school_year": timezone.now().year,
            "term": "1학기",
            "school_stage": TimetableSchoolProfile.SchoolStage.ELEMENTARY,
            "days_text": ",".join(DEFAULT_DAY_KEYS),
        },
    )

    if request.method == "POST" and request.POST.get("action") == "create_workspace_batch":
        if workspace_form.is_valid():
            school = school_map.get(workspace_form.cleaned_data["school_slug"])
            if not school:
                workspace_form.add_error("school_slug", "선택한 학교를 찾지 못했습니다.")
            else:
                try:
                    class_counts = _extract_class_counts(request, workspace_form.resolve_grade_range())
                    created_workspaces = _create_batch_workspaces(
                        school=school,
                        form=workspace_form,
                        class_counts=class_counts,
                        user=request.user,
                    )
                    messages.success(
                        request,
                        f"{school.name} {len(created_workspaces)}개 학년 시간표와 반별 입력 링크를 만들었습니다.",
                    )
                    return redirect("timetable:workspace_detail", workspace_id=created_workspaces[0].id)
                except (IntegrityError, ValidationError) as error:
                    workspace_form.add_error(None, "; ".join(error.messages) if hasattr(error, "messages") else str(error))

    workspaces = list(_get_accessible_workspaces(request))
    school_profiles = {item.school_id: item for item in TimetableSchoolProfile.objects.filter(school_id__in=[workspace.school_id for workspace in workspaces])}
    response = render(
        request,
        "timetable/index.html",
        {
            "service": service,
            "requires_login": False,
            "workspace_form": workspace_form,
            "workspaces": workspaces,
            "school_profiles": school_profiles,
            "batch_setup_url": reverse("timetable:api_setup_batch_create"),
        },
    )
    return _apply_workspace_cache_headers(response)


@login_required
def workspace_detail(request, workspace_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    teacher_form = TimetableTeacherForm(
        request.POST if request.method == "POST" and request.POST.get("action") == "add_teacher" else None
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "add_teacher":
            if teacher_form.is_valid():
                TimetableTeacher.objects.create(
                    school=workspace.school,
                    name=teacher_form.cleaned_data["name"],
                    teacher_type=teacher_form.cleaned_data["teacher_type"],
                    target_weekly_hours=teacher_form.cleaned_data["target_weekly_hours"],
                    subjects_json=teacher_form.cleaned_data["subjects_text"],
                )
                messages.success(request, "교사 정보를 추가했습니다.")
                return redirect("timetable:workspace_detail", workspace_id=workspace.id)
        elif action == "save_room_policies":
            for room in _workspace_rooms(workspace):
                raw_value = request.POST.get(f"room_policy_{room.id}") or "1"
                try:
                    capacity = max(1, int(raw_value))
                except (TypeError, ValueError):
                    capacity = 1
                TimetableRoomPolicy.objects.update_or_create(
                    workspace=workspace,
                    special_room=room,
                    defaults={"capacity_per_slot": capacity},
                )
            messages.success(request, "특별실 수용량을 저장했습니다.")
            return redirect("timetable:workspace_detail", workspace_id=workspace.id)

    state = _build_workspace_state(workspace)
    published_links = []
    published_class_links = []
    published_teacher_links = []
    published_portal = None
    if workspace.published_snapshot_id:
        published_portal = _serialize_share_portal(
            request,
            TimetableSharePortal.objects.filter(snapshot_id=workspace.published_snapshot_id, is_active=True).first(),
        )
        published_links = _serialize_share_links(
            request,
            list(
                workspace.published_snapshot.share_links.select_related("classroom", "teacher").order_by(
                    "audience_type",
                    "id",
                )
            ),
        )
        published_class_links, published_teacher_links = _group_serialized_share_links(published_links)

    response = render(
        request,
        "timetable/workspace.html",
        {
            "service": _get_service(),
            "workspace": workspace,
            "teacher_form": teacher_form,
            "classrooms": state["classrooms"],
            "teachers": state["teachers"],
            "rooms": state["rooms"],
            "room_policies": state["room_policies"],
            "validation": serialize_validation_result(state["validation"]),
            "teacher_stats": _serialize_teacher_stats(state["teacher_stats"]),
            "effective_events": _serialize_effective_events(state["effective_events"]),
            "class_input_rows": _serialize_classroom_input_rows(request, workspace),
            "date_override_count": len(state["date_overrides"]),
            "editor_bootstrap": {
                "classrooms": [{"id": classroom.id, "label": classroom.label} for classroom in state["classrooms"]],
                "days": list(workspace.day_keys),
                "period_labels": list(workspace.period_labels),
                "autosave_url": reverse("timetable:api_autosave", args=[workspace.id]),
                "validate_url": reverse("timetable:api_validate", args=[workspace.id]),
                "snapshots_url": reverse("timetable:api_snapshots", args=[workspace.id]),
                "publish_url": reverse("timetable:api_publish", args=[workspace.id]),
                "events_url": reverse("timetable:api_events", args=[workspace.id]),
                "event_detail_url_template": reverse("timetable:api_event_detail", args=[workspace.id, 0]).replace("/0", "/__EVENT_ID__"),
                "class_link_issue_url": reverse("timetable:api_issue_class_link", args=[workspace.id]),
            },
            "snapshots": [
                _serialize_snapshot_summary(
                    request,
                    workspace,
                    snapshot,
                    is_published=workspace.published_snapshot_id == snapshot.id,
                )
                for snapshot in workspace.snapshots.select_related("created_by")[:10]
            ],
            "published_portal": published_portal,
            "published_class_links": published_class_links,
            "published_teacher_links": published_teacher_links,
            "legacy_import_url": f"{reverse('timetable:legacy_import')}?workspace_id={workspace.id}",
        },
    )
    return _apply_workspace_cache_headers(response)


@login_required
@require_POST
def api_autosave(request, workspace_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error("JSON 형식이 올바르지 않습니다.")
    sheet_data = payload.get("sheet_data")
    if not isinstance(sheet_data, list):
        return _json_error("sheet_data가 필요합니다.")

    state = _persist_workspace_sheet_data(workspace, sheet_data, user=request.user)
    return JsonResponse(
        {
            "ok": True,
            "validation": serialize_validation_result(state["validation"]),
            "teacher_stats": _serialize_teacher_stats(state["teacher_stats"]),
            "updated_at": workspace.updated_at.isoformat(),
        }
    )


@login_required
@require_POST
def api_validate(request, workspace_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error("JSON 형식이 올바르지 않습니다.")
    sheet_data = payload.get("sheet_data")

    if isinstance(sheet_data, list):
        _classrooms, teachers, _rooms, runtime_assignments, issues = _build_runtime_assignments(workspace, sheet_data)
        room_policies = _ensure_room_policies(workspace)
        validation = validate_workspace_assignments(
            workspace,
            runtime_assignments,
            room_policies,
            issues=issues,
            effective_events=_build_effective_events(workspace),
        )
        teacher_stats = build_teacher_stat_rows(teachers, runtime_assignments)
    else:
        state = _build_workspace_state(workspace)
        validation = state["validation"]
        teacher_stats = state["teacher_stats"]

    return JsonResponse(
        {
            "ok": True,
            "validation": serialize_validation_result(validation),
            "teacher_stats": _serialize_teacher_stats(teacher_stats),
        }
    )


@login_required
@require_POST
def api_setup_batch_create(request):
    school_choices, school_map = _get_school_choices(request)
    form = WorkspaceBatchCreateForm(request.POST, school_choices=school_choices)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    school = school_map.get(form.cleaned_data["school_slug"])
    if not school:
        return _json_error("선택한 학교를 찾지 못했습니다.")
    try:
        class_counts = _extract_class_counts(request, form.resolve_grade_range())
        created_workspaces = _create_batch_workspaces(
            school=school,
            form=form,
            class_counts=class_counts,
            user=request.user,
        )
    except (IntegrityError, ValidationError) as error:
        message = "; ".join(error.messages) if hasattr(error, "messages") else str(error)
        return _json_error(message)
    return JsonResponse(
        {
            "ok": True,
            "created_count": len(created_workspaces),
            "redirect_url": reverse("timetable:workspace_detail", args=[created_workspaces[0].id]),
        }
    )


@login_required
@require_POST
def api_issue_class_link(request, workspace_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    payload = _request_payload(request)
    if payload is None:
        return _json_error("요청 형식을 다시 확인해 주세요.")
    classroom = get_object_or_404(
        TimetableClassroom,
        pk=payload.get("classroom_id"),
        school=workspace.school,
        school_year=workspace.school_year,
        grade=workspace.grade,
    )
    link, _created = TimetableClassEditLink.objects.get_or_create(
        workspace=workspace,
        classroom=classroom,
        defaults={
            "issued_by": request.user,
            "expires_at": _default_class_link_expiry(workspace),
        },
    )
    link.token = link.token if not link.pk else TimetableClassEditLink._meta.get_field("token").default()
    link.is_active = True
    link.issued_by = request.user
    link.expires_at = _default_class_link_expiry(workspace)
    link.save(update_fields=["token", "is_active", "issued_by", "expires_at", "updated_at"])
    return JsonResponse(
        {
            "ok": True,
            "link_url": request.build_absolute_uri(reverse("timetable:class_edit", args=[link.token])),
        }
    )


@login_required
@require_POST
def api_revoke_class_link(request, workspace_id, link_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    link = get_object_or_404(TimetableClassEditLink, pk=link_id, workspace=workspace)
    link.is_active = False
    link.save(update_fields=["is_active", "updated_at"])
    return JsonResponse({"ok": True})


@login_required
@require_POST
def api_review_class_status(request, workspace_id, classroom_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    classroom = get_object_or_404(
        TimetableClassroom,
        pk=classroom_id,
        school=workspace.school,
        school_year=workspace.school_year,
        grade=workspace.grade,
    )
    payload = _request_payload(request)
    review_note = str((payload or {}).get("review_note") or "").strip()
    current_status = TimetableClassInputStatus.objects.filter(workspace=workspace, classroom=classroom).first()
    status = _update_class_input_status(
        workspace,
        classroom,
        editor_name=current_status.editor_name if current_status else "",
        reviewed=True,
        review_note=review_note,
    )
    return JsonResponse({"ok": True, "status": status.status, "status_label": status.get_status_display()})


@login_required
@require_POST
def api_events(request, workspace_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error("JSON 형식이 올바르지 않습니다.")
    try:
        event = _event_payload_to_instance(workspace, payload, user=request.user)
    except ValidationError as exc:
        return _json_error("; ".join(exc.messages))

    event.save()
    state = _build_workspace_state(workspace)
    return JsonResponse(
        {
            "ok": True,
            "event_id": event.id,
            "effective_events": _serialize_effective_events(state["effective_events"]),
            "validation": serialize_validation_result(state["validation"]),
            "teacher_stats": _serialize_teacher_stats(state["teacher_stats"]),
        }
    )


@login_required
def api_event_detail(request, workspace_id, event_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    event = _get_workspace_event_or_404(workspace, event_id)

    if request.method == "PATCH":
        payload = _parse_json_request(request)
        if payload is None:
            return _json_error("JSON 형식이 올바르지 않습니다.")
        try:
            event = _event_payload_to_instance(workspace, payload, user=request.user, event=event)
        except ValidationError as exc:
            return _json_error("; ".join(exc.messages))
        event.save()
    elif request.method == "DELETE":
        event.delete()
    else:
        return _json_error("지원하지 않는 요청입니다.", status=405)

    state = _build_workspace_state(workspace)
    return JsonResponse(
        {
            "ok": True,
            "effective_events": _serialize_effective_events(state["effective_events"]),
            "validation": serialize_validation_result(state["validation"]),
            "teacher_stats": _serialize_teacher_stats(state["teacher_stats"]),
        }
    )


@login_required
@require_POST
def api_snapshots(request, workspace_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error("JSON 형식이 올바르지 않습니다.")
    name = (payload.get("name") or "").strip() or timezone.now().strftime("스냅샷_%m%d_%H%M")
    snapshot = _create_snapshot(workspace, created_by=request.user, name=name)
    return JsonResponse(
        {
            "ok": True,
            "snapshot": {
                "id": snapshot.id,
                "name": snapshot.name,
                "created_at": snapshot.created_at.isoformat(),
            },
        }
    )


@login_required
@require_POST
def api_snapshot_restore(request, workspace_id, snapshot_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    snapshot = get_object_or_404(TimetableSnapshot, pk=snapshot_id, workspace=workspace)
    with transaction.atomic():
        _persist_workspace_sheet_data(workspace, snapshot.sheet_data or [], user=request.user)
        _restore_snapshot_date_overrides(workspace, snapshot)
        workspace.status = TimetableWorkspace.Status.DRAFT
        workspace.save(update_fields=["status", "updated_at"])
    state = _build_workspace_state(workspace)
    return JsonResponse(
        {
            "ok": True,
            "snapshot": {"id": snapshot.id, "name": snapshot.name},
            "validation": serialize_validation_result(state["validation"]),
            "teacher_stats": _serialize_teacher_stats(state["teacher_stats"]),
            "redirect_url": reverse("timetable:workspace_detail", args=[workspace.id]),
        }
    )


@login_required
@require_POST
def api_publish(request, workspace_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error("JSON 형식이 올바르지 않습니다.")
    if isinstance(payload.get("sheet_data"), list):
        state = _persist_workspace_sheet_data(workspace, payload["sheet_data"], user=request.user)
    else:
        state = _build_workspace_state(workspace)

    if _has_blocking_conflicts(state["validation"]):
        return _json_validation_error(
            "빨간 경고를 해결한 뒤 확정해 주세요.",
            validation=state["validation"],
            teacher_stats=state["teacher_stats"],
            status=409,
        )

    name = (payload.get("name") or "").strip() or timezone.now().strftime("확정본_%m%d_%H%M")
    snapshot = _create_snapshot(workspace, created_by=request.user, name=name)
    publish_result = publish_to_reservations(snapshot)
    share_portal = _create_share_portal(snapshot)
    share_links = _create_share_links(snapshot)
    workspace.status = TimetableWorkspace.Status.PUBLISHED
    workspace.published_snapshot = snapshot
    workspace.updated_by = request.user
    workspace.save(update_fields=["status", "published_snapshot", "updated_by", "updated_at"])

    return JsonResponse(
        {
            "ok": True,
            "publish_result": publish_result,
            "portal_url": _serialize_share_portal(request, share_portal)["url"],
            "share_links": _serialize_share_links(request, share_links),
            "snapshot": {"id": snapshot.id, "name": snapshot.name},
        }
    )


@login_required
@require_GET
def meeting_view(request, workspace_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    state = _build_workspace_state(workspace)
    teachers = state["teachers"]
    teacher = None
    teacher_id = request.GET.get("teacher")
    if teacher_id:
        for candidate in teachers:
            if str(candidate.id) == str(teacher_id):
                teacher = candidate
                break
    if teacher is None and teachers:
        teacher = teachers[0]
    selected_date = _parse_iso_date(request.GET.get("date"))
    if selected_date and workspace.term_start_date and selected_date < workspace.term_start_date:
        selected_date = workspace.term_start_date
    if selected_date and workspace.term_end_date and selected_date > workspace.term_end_date:
        selected_date = workspace.term_end_date
    matrix = build_meeting_matrix(
        workspace,
        teacher,
        state["classrooms"],
        state["assignments"],
        state["effective_events"],
        target_date=selected_date,
        date_overrides=state["date_overrides"],
    ) if teacher else {"slots": [], "rows": []}

    response = render(
        request,
        "timetable/meeting.html",
        {
            "workspace": workspace,
            "teachers": teachers,
            "selected_teacher": teacher,
            "rooms": state["rooms"],
            "meeting_matrix": matrix,
            "selected_date": selected_date,
            "selected_week_label": build_week_label(workspace, selected_date) if selected_date else "",
        },
    )
    return _apply_workspace_cache_headers(response)


@login_required
@require_POST
def api_meeting_apply(request, workspace_id):
    workspace = _get_editable_workspace_or_404(request, workspace_id)
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error("JSON 형식이 올바르지 않습니다.")

    teacher = get_object_or_404(TimetableTeacher, pk=payload.get("teacher_id"), school=workspace.school)
    subject_name = (payload.get("subject_name") or "").strip()
    if not subject_name:
        return _json_error("과목 이름을 입력해 주세요.")
    selections = payload.get("selections") or []
    if not isinstance(selections, list) or not selections:
        return _json_error("적용할 칸을 선택해 주세요.")
    room = None
    room_id = payload.get("room_id")
    if room_id:
        room = get_object_or_404(SpecialRoom, pk=room_id, school=workspace.school)
    target_date = _parse_iso_date(payload.get("date"))
    if target_date and workspace.term_start_date and target_date < workspace.term_start_date:
        return _json_error("학기 시작일 이후 날짜를 선택해 주세요.")
    if target_date and workspace.term_end_date and target_date > workspace.term_end_date:
        return _json_error("학기 안의 날짜만 선택해 주세요.")

    preview = _build_meeting_apply_preview(
        workspace,
        teacher,
        subject_name,
        room,
        selections,
        target_date=target_date,
    )
    if _has_blocking_conflicts(preview["validation"]):
        return _json_validation_error(
            "충돌을 해결한 뒤 회의 배정을 반영해 주세요.",
            validation=preview["validation"],
            teacher_stats=preview["teacher_stats"],
            status=409,
        )

    apply_meeting_selections(
        workspace,
        teacher,
        subject_name,
        room,
        preview["normalized_selections"],
        target_date=target_date,
    )
    if not target_date:
        workspace.sheet_data = assignments_to_sheet_data(workspace)
    workspace.updated_by = request.user
    workspace.status = TimetableWorkspace.Status.DRAFT
    update_fields = ["updated_by", "status", "updated_at"]
    if not target_date:
        update_fields.insert(0, "sheet_data")
    workspace.save(update_fields=update_fields)

    state = _build_workspace_state(workspace)
    return JsonResponse(
        {
            "ok": True,
            "applied_count": len(preview["normalized_selections"]),
            "validation": serialize_validation_result(state["validation"]),
            "teacher_stats": _serialize_teacher_stats(state["teacher_stats"]),
            "redirect_url": reverse("timetable:workspace_detail", args=[workspace.id]),
        }
    )


def class_edit_view(request, token):
    link = _get_public_class_edit_link_or_404(token)
    workspace = link.workspace
    classroom = link.classroom
    link.last_accessed_at = timezone.now()
    link.save(update_fields=["last_accessed_at", "updated_at"])

    state = _build_workspace_state(workspace)
    current_status, _created = TimetableClassInputStatus.objects.get_or_create(workspace=workspace, classroom=classroom)
    mode = (request.GET.get("mode") or "weekly").strip()
    if mode not in {"weekly", "daily"}:
        mode = "weekly"
    selected_date = _parse_iso_date(request.GET.get("date")) or workspace.term_start_date or timezone.localdate()
    if workspace.term_end_date and selected_date > workspace.term_end_date:
        selected_date = workspace.term_end_date
    weekly_rows = _build_classroom_weekly_rows(workspace, classroom)
    daily_rows = build_classroom_date_rows(
        workspace,
        classroom,
        selected_date,
        state["assignments"],
        state["date_overrides"],
        state["effective_events"],
    )
    serialized_overrides = build_serialized_date_overrides(
        workspace,
        [item for item in state["date_overrides"] if item.classroom_id == classroom.id],
    )
    today_iso = timezone.localdate().isoformat()
    upcoming_overrides = [item for item in serialized_overrides if item["date"] >= today_iso]
    response = render(
        request,
        "timetable/class_edit.html",
        {
            "workspace": workspace,
            "classroom": classroom,
            "link": link,
            "input_status": current_status,
            "mode": mode,
            "weekly_rows": weekly_rows,
            "selected_date": selected_date,
            "selected_week_label": build_week_label(workspace, selected_date),
            "daily_rows": daily_rows,
            "upcoming_overrides": upcoming_overrides[:8],
            "edit_bootstrap": {
                "weekly_save_url": reverse("timetable:api_class_edit_weekly_autosave", args=[link.token]),
                "daily_save_url": reverse("timetable:api_class_edit_date_override_autosave", args=[link.token]),
                "submit_url": reverse("timetable:api_class_edit_submit", args=[link.token]),
                "selected_date": selected_date.isoformat(),
                "mode": mode,
            },
            "robots": "noindex,nofollow",
        },
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return _apply_sensitive_cache_headers(response)


@require_POST
def api_class_edit_weekly_autosave(request, token):
    link = _get_public_class_edit_link_or_404(token)
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error("JSON 형식을 다시 확인해 주세요.")
    try:
        editor_name = _resolve_class_editor_name(link.workspace, link.classroom, payload)
        entries = _normalize_weekly_entries(link.workspace, payload)
    except ValidationError as error:
        return _json_error("; ".join(error.messages))
    result = _persist_class_weekly_entries(
        link.workspace,
        link.classroom,
        entries,
        editor_name=editor_name,
        submitted=False,
    )
    return JsonResponse(
        {
            "ok": True,
            "validation": serialize_validation_result(result["validation"]),
            "teacher_stats": _serialize_teacher_stats(result["teacher_stats"]),
            "redirect_url": result["redirect_url"],
        }
    )


@require_POST
def api_class_edit_date_override_autosave(request, token):
    link = _get_public_class_edit_link_or_404(token)
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error("JSON 형식을 다시 확인해 주세요.")
    target_date = _parse_iso_date(payload.get("date"))
    if not target_date:
        return _json_error("날짜를 다시 선택해 주세요.")
    try:
        editor_name = _resolve_class_editor_name(link.workspace, link.classroom, payload)
        entries = _normalize_date_override_entries(link.workspace, payload)
    except ValidationError as error:
        return _json_error("; ".join(error.messages))
    result = _persist_class_date_override_entries(
        link.workspace,
        link.classroom,
        target_date,
        entries,
        editor_name=editor_name,
        submitted=False,
    )
    return JsonResponse(
        {
            "ok": True,
            "validation": serialize_validation_result(result["validation"]),
            "teacher_stats": _serialize_teacher_stats(result["teacher_stats"]),
            "redirect_url": result["redirect_url"],
        }
    )


@require_POST
def api_class_edit_submit(request, token):
    link = _get_public_class_edit_link_or_404(token)
    payload = _parse_json_request(request)
    if payload is None:
        return _json_error("JSON 형식을 다시 확인해 주세요.")
    mode = str(payload.get("mode") or "weekly").strip()
    try:
        editor_name = _resolve_class_editor_name(link.workspace, link.classroom, payload)
        if mode == "daily":
            target_date = _parse_iso_date(payload.get("date"))
            if not target_date:
                return _json_error("날짜를 다시 선택해 주세요.")
            entries = _normalize_date_override_entries(link.workspace, payload)
            result = _persist_class_date_override_entries(
                link.workspace,
                link.classroom,
                target_date,
                entries,
                editor_name=editor_name,
                submitted=True,
            )
        else:
            entries = _normalize_weekly_entries(link.workspace, payload)
            result = _persist_class_weekly_entries(
                link.workspace,
                link.classroom,
                entries,
                editor_name=editor_name,
                submitted=True,
            )
    except ValidationError as error:
        return _json_error("; ".join(error.messages))
    return JsonResponse(
        {
            "ok": True,
            "validation": serialize_validation_result(result["validation"]),
            "teacher_stats": _serialize_teacher_stats(result["teacher_stats"]),
            "redirect_url": result["redirect_url"],
        }
    )


def share_portal_view(request, token):
    portal = get_object_or_404(
        TimetableSharePortal.objects.select_related("snapshot", "snapshot__workspace"),
        token=token,
        is_active=True,
    )
    if portal.is_expired:
        raise Http404

    sections = _build_share_portal_sections(request, portal)
    response = render(
        request,
        "timetable/share_portal.html",
        {
            "portal": portal,
            "workspace": portal.snapshot.workspace,
            "snapshot": portal.snapshot,
            "class_links": sections["class_links"],
            "teacher_links": sections["teacher_links"],
            "robots": "noindex,nofollow",
        },
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return _apply_sensitive_cache_headers(response)


def share_view(request, token):
    link = get_object_or_404(
        TimetableShareLink.objects.select_related(
            "snapshot",
            "snapshot__workspace",
            "classroom",
            "teacher",
        ),
        token=token,
        is_active=True,
    )
    if link.is_expired:
        raise Http404

    snapshot = link.snapshot
    workspace = snapshot.workspace
    teacher_lookup = {teacher.name: teacher for teacher in _workspace_teachers(workspace)}
    if link.audience_type == TimetableShareLink.AudienceType.CLASSROOM:
        if not link.classroom:
            raise Http404
        title = f"{link.classroom.label} 주간 시간표"
        rows = _build_class_share_rows(snapshot, link.classroom, teacher_lookup)
        upcoming_overrides = _build_share_upcoming_overrides(snapshot, classroom=link.classroom)
        audience_label = link.classroom.label
        audience_type = "class"
    else:
        if not link.teacher:
            raise Http404
        title = f"{link.teacher.name} 교사 시간표"
        rows = _build_teacher_share_rows(snapshot, link.teacher)
        upcoming_overrides = _build_share_upcoming_overrides(snapshot, teacher=link.teacher)
        audience_label = link.teacher.name
        audience_type = "teacher"

    response = render(
        request,
        "timetable/share.html",
        {
            "workspace": workspace,
            "snapshot": snapshot,
            "title": title,
            "audience_label": audience_label,
            "audience_type": audience_type,
            "rows": rows,
            "upcoming_overrides": upcoming_overrides,
            "robots": "noindex,nofollow",
        },
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    return _apply_sensitive_cache_headers(response)


@login_required
def legacy_import(request):
    workspace = None
    workspace_id = request.GET.get("workspace_id") or request.POST.get("workspace_id")
    if workspace_id:
        workspace = _get_editable_workspace_or_404(request, workspace_id)

    school_choices, _school_map = _get_school_choices(request)
    workspaces = list(_get_accessible_workspaces(request))
    check_result = None
    generated_result = None

    if request.method == "POST":
        file_obj = request.FILES.get("excel_file")
        if not file_obj:
            messages.error(request, "엑셀 파일을 선택해 주세요.")
        else:
            check_result = validate_timetable_workbook(file_obj)
            if check_result["is_valid"]:
                generated_result = generate_timetable_schedule(file_obj)
                if generated_result["is_success"] and workspace:
                    classrooms = _workspace_classrooms(workspace)
                    workspace.days_json = list(generated_result.get("days") or workspace.day_keys)
                    workspace.period_labels_json = list(generated_result.get("slot_labels") or workspace.period_labels)
                    workspace.sheet_data = legacy_generated_result_to_sheet_data(workspace, generated_result, classrooms)
                    workspace.updated_by = request.user
                    workspace.status = TimetableWorkspace.Status.DRAFT
                    workspace.save(
                        update_fields=["days_json", "period_labels_json", "sheet_data", "updated_by", "status", "updated_at"]
                    )
                    _persist_workspace_sheet_data(
                        workspace,
                        workspace.sheet_data,
                        user=request.user,
                        source=TimetableSlotAssignment.Source.IMPORT,
                    )
                    messages.success(request, "엑셀 결과를 현재 시간표로 가져왔습니다.")
                    return redirect("timetable:workspace_detail", workspace_id=workspace.id)
                if generated_result["is_success"]:
                    messages.success(request, "엑셀 점검과 자동 배치가 완료되었습니다.")
                else:
                    messages.warning(request, "자동 배치 일부를 확인해 주세요.")
            else:
                messages.error(request, "입력 형식을 먼저 수정해 주세요.")

    response = render(
        request,
        "timetable/legacy/import.html",
        {
            "workspace": workspace,
            "workspaces": workspaces,
            "check_result": check_result,
            "generated_result": generated_result,
            "school_choices": school_choices,
        },
    )
    return _apply_workspace_cache_headers(response)
