import re

from timetable.models import DEFAULT_DAY_KEYS


DISPLAY_TEXT_RE = re.compile(
    r"^\s*(?P<subject>[^(@\[][^@]*?)(?:\((?P<teacher>[^)]+)\))?(?:\s*@\s*(?P<room>.+))?\s*$"
)


def build_default_period_labels(period_count):
    return [f"{idx}교시" for idx in range(1, int(period_count) + 1)]


def classroom_sheet_name(classroom):
    return classroom.label


def build_display_text(subject_name="", teacher_name="", room_name=""):
    subject = (subject_name or "").strip()
    teacher = (teacher_name or "").strip()
    room = (room_name or "").strip()
    if not subject and not teacher and not room:
        return ""
    base = subject or ""
    if teacher:
        base = f"{base}({teacher})" if base else f"({teacher})"
    if room:
        base = f"{base} @ {room}" if base else f"@ {room}"
    return base.strip()


def parse_display_text(text):
    raw = str(text or "").strip()
    if not raw:
        return {
            "display_text": "",
            "subject_name": "",
            "teacher_name": "",
            "room_name": "",
            "issues": [],
        }

    match = DISPLAY_TEXT_RE.match(raw)
    if not match:
        return {
            "display_text": raw,
            "subject_name": raw,
            "teacher_name": "",
            "room_name": "",
            "issues": ["형식이 올바르지 않습니다. 예: 영어(홍길동) @ 과학실"],
        }

    subject_name = (match.group("subject") or "").strip()
    teacher_name = (match.group("teacher") or "").strip()
    room_name = (match.group("room") or "").strip()
    issues = []
    if teacher_name and not subject_name:
        issues.append("과목 없이 교사 이름만 입력되었습니다.")
    return {
        "display_text": build_display_text(subject_name, teacher_name, room_name) or raw,
        "subject_name": subject_name,
        "teacher_name": teacher_name,
        "room_name": room_name,
        "issues": issues,
    }


def _cell(value, *, bold=False, bg=None):
    if value in (None, ""):
        return None
    cell = {
        "v": value,
        "m": value,
        "ct": {"fa": "General", "t": "g"},
    }
    if bold:
        cell["bl"] = 1
    if bg:
        cell["bg"] = bg
    return cell


def build_classroom_sheet(workspace, classroom, assignment_lookup):
    days = list(workspace.day_keys)
    period_labels = list(workspace.period_labels)
    row_count = len(period_labels) + 1
    col_count = len(days) + 1
    data = [[None for _ in range(col_count)] for _ in range(row_count)]
    data[0][0] = _cell("교시", bold=True, bg="#E2E8F0")
    for day_index, day_key in enumerate(days, start=1):
        data[0][day_index] = _cell(day_key, bold=True, bg="#DBEAFE")
    for row_index, period_label in enumerate(period_labels, start=1):
        data[row_index][0] = _cell(period_label, bold=True, bg="#F8FAFC")
        for col_index, day_key in enumerate(days, start=1):
            assignment = assignment_lookup.get((classroom.id, day_key, row_index))
            if assignment and assignment.display_text:
                data[row_index][col_index] = _cell(assignment.display_text)

    return {
        "name": classroom_sheet_name(classroom),
        "id": f"classroom-{classroom.id}",
        "order": classroom.class_no,
        "row": row_count,
        "column": col_count,
        "defaultRowHeight": 32,
        "defaultColWidth": 140,
        "showGridLines": 1,
        "data": data,
        "config": {},
    }


def build_workspace_sheet_data(workspace, classrooms, assignments):
    assignment_lookup = {}
    for assignment in assignments:
        assignment_lookup[(assignment.classroom_id, assignment.day_key, assignment.period_no)] = assignment

    active_classrooms = [classroom for classroom in classrooms if classroom.is_active]
    active_classrooms.sort(key=lambda item: (item.grade, item.class_no))
    if not active_classrooms:
        return [
            {
                "name": workspace.grade_label,
                "id": "empty-sheet",
                "row": len(workspace.period_labels) + 1,
                "column": len(workspace.day_keys) + 1,
                "data": [],
                "showGridLines": 1,
            }
        ]
    return [build_classroom_sheet(workspace, classroom, assignment_lookup) for classroom in active_classrooms]


def assignments_to_sheet_data(workspace):
    classrooms = list(
        workspace.school.timetable_classrooms.filter(
            school_year=workspace.school_year,
            grade=workspace.grade,
        ).order_by("class_no", "id")
    )
    assignments = list(workspace.assignments.select_related("classroom", "teacher", "special_room"))
    return build_workspace_sheet_data(workspace, classrooms, assignments)


def _extract_cell_text(cell):
    if not cell:
        return ""
    if isinstance(cell, dict):
        value = cell.get("m")
        if value in (None, ""):
            value = cell.get("v")
        return str(value or "").strip()
    return str(cell).strip()


def normalize_sheet_data(workspace, sheet_data, classrooms, teachers, special_rooms):
    classroom_by_sheet = {classroom_sheet_name(classroom): classroom for classroom in classrooms}
    teacher_by_name = {teacher.name: teacher for teacher in teachers if teacher.is_active}
    room_by_name = {room.name: room for room in special_rooms}
    assignments = []
    issues = []
    seen = set()

    for sheet in sheet_data or []:
        classroom = classroom_by_sheet.get((sheet or {}).get("name"))
        if not classroom:
            issues.append(
                {
                    "kind": "sheet",
                    "message": f"알 수 없는 시트가 포함되어 있어 건너뛰었습니다: {(sheet or {}).get('name') or '이름 없음'}",
                }
            )
            continue

        matrix = list((sheet or {}).get("data") or [])
        for period_no, _period_label in enumerate(workspace.period_labels, start=1):
            row_index = period_no
            row_cells = matrix[row_index] if row_index < len(matrix) else []
            for day_index, day_key in enumerate(workspace.day_keys, start=1):
                raw_text = _extract_cell_text(row_cells[day_index] if day_index < len(row_cells) else None)
                slot_key = (classroom.id, day_key, period_no)
                if slot_key in seen:
                    issues.append(
                        {
                            "kind": "duplicate",
                            "message": f"{classroom.label} {day_key} {period_no}교시가 중복되었습니다.",
                            "cell_key": f"{classroom.id}:{day_key}:{period_no}",
                        }
                    )
                    continue
                seen.add(slot_key)

                parsed = parse_display_text(raw_text)
                if not raw_text and not parsed["subject_name"] and not parsed["teacher_name"] and not parsed["room_name"]:
                    continue

                teacher = teacher_by_name.get(parsed["teacher_name"]) if parsed["teacher_name"] else None
                special_room = room_by_name.get(parsed["room_name"]) if parsed["room_name"] else None
                if parsed["teacher_name"] and not teacher:
                    issues.append(
                        {
                            "kind": "teacher",
                            "message": f"{classroom.label} {day_key} {period_no}교시에 입력한 교사 '{parsed['teacher_name']}'를 찾지 못했습니다.",
                            "cell_key": f"{classroom.id}:{day_key}:{period_no}",
                        }
                    )
                if parsed["room_name"] and not special_room:
                    issues.append(
                        {
                            "kind": "room",
                            "message": f"{classroom.label} {day_key} {period_no}교시에 입력한 특별실 '{parsed['room_name']}'를 찾지 못했습니다.",
                            "cell_key": f"{classroom.id}:{day_key}:{period_no}",
                        }
                    )
                for message in parsed["issues"]:
                    issues.append(
                        {
                            "kind": "format",
                            "message": f"{classroom.label} {day_key} {period_no}교시: {message}",
                            "cell_key": f"{classroom.id}:{day_key}:{period_no}",
                        }
                    )

                assignments.append(
                    {
                        "workspace": workspace,
                        "classroom": classroom,
                        "day_key": day_key,
                        "period_no": period_no,
                        "subject_name": parsed["subject_name"],
                        "teacher": teacher,
                        "special_room": special_room,
                        "display_text": parsed["display_text"] or raw_text,
                        "note": "",
                    }
                )

    return assignments, issues
