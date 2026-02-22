import logging
import random
import csv
from datetime import timedelta
from io import BytesIO, StringIO
from zipfile import ZIP_DEFLATED, ZipFile
from uuid import uuid4

import openpyxl
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from happy_seed.models import HSClassroom, HSStudent
from seed_quiz.models import SQAttempt, SQGenerationLog, SQQuizBank, SQQuizItem, SQQuizSet
from seed_quiz.services.bank import (
    copy_bank_to_draft,
    generate_bank_from_context_ai,
    parse_csv_upload,
    save_parsed_sets_to_bank,
)
from seed_quiz.services.gate import (
    clear_session,
    find_or_create_attempt,
    get_current_item,
    get_today_published_set,
    set_session,
)
from seed_quiz.services.generation import generate_and_save_draft
from seed_quiz.services.grading import submit_and_reward
from seed_quiz.services.rag import consume_rag_quota, refund_rag_quota
from seed_quiz.topics import DEFAULT_TOPIC, TOPIC_LABELS, normalize_topic

logger = logging.getLogger("seed_quiz.views")

CSV_PREVIEW_PAYLOAD_KEY = "sq_csv_preview_payload"
CSV_PREVIEW_TOKEN_KEY = "sq_csv_preview_token"
CSV_ERROR_REPORT_TOKEN_KEY = "sq_csv_error_report_token"
CSV_ERROR_REPORT_ROWS_KEY = "sq_csv_error_report_rows"

CSV_CANONICAL_HEADERS = [
    "set_title",
    "preset_type",
    "grade",
    "question_text",
    "choice_1",
    "choice_2",
    "choice_3",
    "choice_4",
    "correct_index",
    "explanation",
    "difficulty",
]

CSV_KOREAN_HEADERS = [
    "세트코드",
    "주제",
    "학년",
    "문제",
    "보기1",
    "보기2",
    "보기3",
    "보기4",
    "정답번호",
    "해설",
    "난이도",
]

CSV_GUIDE_COLUMNS = [
    {"ko": "세트코드", "en": "set_title", "required": "필수", "desc": "세트 고유 코드 (예: SQ-orthography-basic-L1-G3-S001-V1)"},
    {"ko": "주제", "en": "preset_type", "required": "필수", "desc": "주제 키 또는 한글 주제명 (예: orthography 또는 맞춤법)"},
    {"ko": "학년", "en": "grade", "required": "필수", "desc": "1~6 숫자"},
    {"ko": "문제", "en": "question_text", "required": "필수", "desc": "문항 본문"},
    {"ko": "보기1", "en": "choice_1", "required": "필수", "desc": "선택지 1"},
    {"ko": "보기2", "en": "choice_2", "required": "필수", "desc": "선택지 2"},
    {"ko": "보기3", "en": "choice_3", "required": "필수", "desc": "선택지 3"},
    {"ko": "보기4", "en": "choice_4", "required": "필수", "desc": "선택지 4"},
    {"ko": "정답번호", "en": "correct_index", "required": "필수", "desc": "0~3 (보기1=0, 보기2=1, 보기3=2, 보기4=3)"},
    {"ko": "해설", "en": "explanation", "required": "선택", "desc": "정답 설명"},
    {"ko": "난이도", "en": "difficulty", "required": "선택", "desc": "쉬움/보통/어려움 또는 easy/medium/hard"},
]

CSV_XLSX_COLUMN_WIDTHS = [36, 16, 8, 42, 22, 22, 22, 22, 12, 36, 12]


def _get_positive_int_setting(name: str, default: int) -> int:
    try:
        value = int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _get_csv_upload_limits() -> dict:
    return {
        "max_file_bytes": _get_positive_int_setting("SEED_QUIZ_CSV_MAX_FILE_BYTES", 2 * 1024 * 1024),
        "max_rows": _get_positive_int_setting("SEED_QUIZ_CSV_MAX_ROWS", 1200),
        "max_sets": _get_positive_int_setting("SEED_QUIZ_CSV_MAX_SETS", 400),
    }


def _humanize_bytes(num: int) -> str:
    value = float(max(0, int(num)))
    units = ["B", "KB", "MB", "GB"]
    unit_idx = 0
    while value >= 1024 and unit_idx < len(units) - 1:
        value /= 1024
        unit_idx += 1
    if unit_idx == 0:
        return f"{int(value)}{units[unit_idx]}"
    return f"{value:.1f}{units[unit_idx]}"


def _trim_errors(errors: list[str], max_items: int = 5, max_len: int = 180) -> list[str]:
    trimmed = []
    for err in (errors or [])[:max_items]:
        msg = str(err or "").replace("\n", " ").replace("\r", " ").strip()
        if len(msg) > max_len:
            msg = msg[: max_len - 1] + "..."
        if msg:
            trimmed.append(msg)
    return trimmed


def _log_csv_event(
    *,
    classroom,
    teacher,
    code: str,
    level: str,
    message: str,
    payload: dict | None = None,
):
    data = dict(payload or {})
    data.setdefault("classroom_id", str(classroom.id))
    data.setdefault("teacher_id", int(getattr(teacher, "id", 0) or 0))
    SQGenerationLog.objects.create(
        level=level,
        code=code,
        message=message,
        payload=data,
    )


def _parse_bank_filters(raw_preset: str, raw_grade: str):
    preset_type = normalize_topic(raw_preset) or DEFAULT_TOPIC
    raw_grade_value = (raw_grade or "").strip().lower()
    if raw_grade_value in {"all", "*", ""}:
        return preset_type, None
    try:
        grade = int(raw_grade_value)
    except (TypeError, ValueError):
        grade = 3
    if grade not in range(1, 7):
        grade = 3
    return preset_type, grade


def _build_bank_queryset(classroom, user, preset_type: str, grade: int | None, scope: str):
    banks_qs = SQQuizBank.objects.filter(
        is_active=True,
        preset_type=preset_type,
    )
    if grade is not None:
        banks_qs = banks_qs.filter(grade=grade)

    approved_filter = Q(quality_status="approved")
    today = timezone.localdate()
    available_filter = (
        (Q(available_from__isnull=True) | Q(available_from__lte=today))
        & (Q(available_to__isnull=True) | Q(available_to__gte=today))
    )
    if scope == "official":
        banks_qs = banks_qs.filter(is_official=True).filter(approved_filter).filter(available_filter)
    elif scope == "public":
        banks_qs = banks_qs.filter(is_public=True).filter(approved_filter).filter(available_filter)
    else:
        banks_qs = banks_qs.filter(
            (Q(is_official=True) & approved_filter & available_filter)
            | (Q(is_public=True) & approved_filter & available_filter)
            | Q(created_by=user)
        ).distinct()
    return banks_qs


def _clear_csv_error_report(request):
    request.session.pop(CSV_ERROR_REPORT_TOKEN_KEY, None)
    request.session.pop(CSV_ERROR_REPORT_ROWS_KEY, None)
    request.session.modified = True


def _store_csv_error_report(request, errors: list[str]) -> str:
    token = uuid4().hex
    sanitized = []
    for raw in errors:
        msg = str(raw or "").replace("\r", " ").replace("\n", " ").strip()
        if msg:
            sanitized.append(msg)
    request.session[CSV_ERROR_REPORT_TOKEN_KEY] = token
    request.session[CSV_ERROR_REPORT_ROWS_KEY] = sanitized[:500]
    request.session.modified = True
    return token


# ---------------------------------------------------------------------------
# 랜딩
# ---------------------------------------------------------------------------

@login_required
def landing(request):
    """제품 카드 클릭 시 happy_seed 대시보드로 이동."""
    return redirect("happy_seed:dashboard")


# ---------------------------------------------------------------------------
# 교사 뷰
# ---------------------------------------------------------------------------

@login_required
def teacher_dashboard(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    csv_limits = _get_csv_upload_limits()
    initial_preset, initial_grade = _parse_bank_filters(
        request.GET.get("preset_type", DEFAULT_TOPIC),
        request.GET.get("grade", "3"),
    )
    today_sets = SQQuizSet.objects.filter(
        classroom=classroom,
        target_date=timezone.localdate(),
    ).order_by("-created_at")
    return render(
        request,
        "seed_quiz/teacher_dashboard.html",
        {
            "classroom": classroom,
            "today_sets": today_sets,
            "preset_choices": SQQuizSet.PRESET_CHOICES,
            "initial_preset": initial_preset,
            "initial_grade": initial_grade,
            "initial_grade_str": "all" if initial_grade is None else str(initial_grade),
            "rag_daily_limit": max(0, int(getattr(settings, "SEED_QUIZ_RAG_DAILY_LIMIT", 1))),
            "allow_rag": bool(getattr(settings, "SEED_QUIZ_ALLOW_RAG", False)),
            "csv_limits": csv_limits,
            "csv_limits_human": {
                "max_file": _humanize_bytes(csv_limits["max_file_bytes"]),
                "max_rows": csv_limits["max_rows"],
                "max_sets": csv_limits["max_sets"],
            },
            "csv_headers_ko_text": ",".join(CSV_KOREAN_HEADERS),
            "csv_headers_en_text": ",".join(CSV_CANONICAL_HEADERS),
            "csv_guide_columns": CSV_GUIDE_COLUMNS,
        },
    )


@login_required
def download_csv_guide(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    if not classroom:
        return HttpResponseForbidden("권한이 없습니다.")
    return render(
        request,
        "seed_quiz/csv_guide.html",
        {
            "classroom": classroom,
            "csv_headers_ko_text": ",".join(CSV_KOREAN_HEADERS),
            "csv_headers_en_text": ",".join(CSV_CANONICAL_HEADERS),
            "csv_guide_columns": CSV_GUIDE_COLUMNS,
        },
    )


@login_required
def download_csv_template(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    if not classroom:
        return HttpResponseForbidden("권한이 없습니다.")

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_KOREAN_HEADERS)
    for topic_key, topic_label in SQQuizSet.PRESET_CHOICES:
        set_title = f"SQ-{topic_key}-basic-L1-G3-S001-V1"
        for q_no in range(1, 4):
            writer.writerow(
                [
                    set_title,
                    topic_key,
                    3,
                    f"[{topic_label}] 예시 문제 {q_no}",
                    f"{topic_label} 보기 A{q_no}",
                    f"{topic_label} 보기 B{q_no}",
                    f"{topic_label} 보기 C{q_no}",
                    f"{topic_label} 보기 D{q_no}",
                    (q_no - 1) % 4,
                    f"{topic_label} 예시 해설 {q_no}",
                    "쉬움",
                ]
            )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="seed_quiz_template.csv"'
    response.write("\ufeff")
    response.write(output.getvalue())
    return response


@login_required
def download_xlsx_template(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    if not classroom:
        return HttpResponseForbidden("권한이 없습니다.")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "씨앗퀴즈 템플릿"
    ws.append(CSV_KOREAN_HEADERS)

    header_fill = PatternFill(fill_type="solid", start_color="E8F0FE", end_color="E8F0FE")
    for col_idx, header in enumerate(CSV_KOREAN_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True, color="1F2937")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = CSV_XLSX_COLUMN_WIDTHS[col_idx - 1]

    row_no = 2
    for topic_key, topic_label in SQQuizSet.PRESET_CHOICES:
        set_title = f"SQ-{topic_key}-basic-L1-G3-S001-V1"
        for q_no in range(1, 4):
            ws.append(
                [
                    set_title,
                    topic_label,
                    3,
                    f"[{topic_label}] 예시 문제 {q_no}",
                    f"{topic_label} 보기 A{q_no}",
                    f"{topic_label} 보기 B{q_no}",
                    f"{topic_label} 보기 C{q_no}",
                    f"{topic_label} 보기 D{q_no}",
                    (q_no - 1) % 4,
                    f"{topic_label} 예시 해설 {q_no}",
                    "쉬움",
                ]
            )
            for col_idx in range(1, len(CSV_KOREAN_HEADERS) + 1):
                ws.cell(row=row_no, column=col_idx).alignment = Alignment(vertical="top", wrap_text=True)
            row_no += 1

    ws.freeze_panes = "A2"

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="seed_quiz_template.xlsx"'
    return response


@login_required
def download_csv_sample_pack(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    if not classroom:
        return HttpResponseForbidden("권한이 없습니다.")

    headers = CSV_KOREAN_HEADERS

    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as zf:
        readme_lines = [
            "Seed Quiz CSV 샘플 팩",
            "",
            "- 모든 파일은 현재 업로드 검증 규칙을 통과하도록 구성되어 있습니다.",
            "- 각 CSV는 1세트(3문항)이며, set_title 규칙을 따릅니다.",
            "- 한글 헤더/영문 헤더 모두 업로드 가능합니다.",
            "- 필요 시 문항/보기/해설을 수정해 업로드하세요.",
        ]
        zf.writestr("README.txt", "\n".join(readme_lines))

        for idx, (topic_key, topic_label) in enumerate(SQQuizSet.PRESET_CHOICES, start=1):
            seq_no = 900 + idx
            set_title = f"SQ-{topic_key}-basic-L1-G3-S{seq_no:03d}-V1"
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(headers)
            writer.writerow(
                [
                    set_title,
                    topic_key,
                    3,
                    f"[{topic_label}] 예시 문제 1",
                    f"{topic_label} 정답 1",
                    f"{topic_label} 오답 1-1",
                    f"{topic_label} 오답 1-2",
                    f"{topic_label} 오답 1-3",
                    0,
                    f"{topic_label} 예시 해설 1",
                    "쉬움",
                ]
            )
            writer.writerow(
                [
                    set_title,
                    topic_key,
                    3,
                    f"[{topic_label}] 예시 문제 2",
                    f"{topic_label} 오답 2-1",
                    f"{topic_label} 정답 2",
                    f"{topic_label} 오답 2-2",
                    f"{topic_label} 오답 2-3",
                    1,
                    f"{topic_label} 예시 해설 2",
                    "쉬움",
                ]
            )
            writer.writerow(
                [
                    set_title,
                    topic_key,
                    3,
                    f"[{topic_label}] 예시 문제 3",
                    f"{topic_label} 오답 3-1",
                    f"{topic_label} 오답 3-2",
                    f"{topic_label} 정답 3",
                    f"{topic_label} 오답 3-3",
                    2,
                    f"{topic_label} 예시 해설 3",
                    "쉬움",
                ]
            )

            csv_text = output.getvalue()
            parsed_sets, errors = parse_csv_upload(csv_text.encode("utf-8"))
            if errors or not parsed_sets:
                return HttpResponse(
                    "샘플 CSV 팩 생성 중 검증 오류가 발생했습니다. 관리자에게 문의해 주세요.",
                    status=500,
                )
            zf.writestr(f"samples/{idx:02d}_{topic_key}.csv", "\ufeff" + csv_text)

    response = HttpResponse(content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="seed_quiz_sample_pack.zip"'
    response.write(buffer.getvalue())
    return response


@login_required
def download_csv_error_report(request, classroom_id, token):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    if not classroom:
        return HttpResponseForbidden("권한이 없습니다.")

    session_token = request.session.get(CSV_ERROR_REPORT_TOKEN_KEY)
    error_rows = request.session.get(CSV_ERROR_REPORT_ROWS_KEY) or []

    if not token or token != session_token or not error_rows:
        return HttpResponse("오류 리포트가 만료되었습니다. 다시 CSV를 업로드해 주세요.", status=404)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["no", "error_message"])
    for idx, message in enumerate(error_rows, start=1):
        writer.writerow([idx, message])

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="seed_quiz_error_report_{timezone.localdate().isoformat()}.csv"'
    )
    response.write("\ufeff")
    response.write(output.getvalue())
    return response


@login_required
def htmx_bank_browse(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    preset_type, grade = _parse_bank_filters(
        request.GET.get("preset_type", DEFAULT_TOPIC),
        request.GET.get("grade", "3"),
    )
    scope = (request.GET.get("scope", "official") or "official").strip().lower()
    if scope not in {"official", "public", "all"}:
        scope = "official"

    banks_qs = _build_bank_queryset(
        classroom=classroom,
        user=request.user,
        preset_type=preset_type,
        grade=grade,
        scope=scope,
    )

    banks = banks_qs.order_by("-is_official", "-use_count", "-created_at")[:24]

    return render(
        request,
        "seed_quiz/partials/bank_browse.html",
        {
            "classroom": classroom,
            "banks": banks,
            "scope": scope,
            "preset_type": preset_type,
            "preset_label": TOPIC_LABELS.get(preset_type, "주제"),
            "grade": grade,
            "allow_inline_ai": bool(getattr(settings, "SEED_QUIZ_ALLOW_INLINE_AI", False)),
        },
    )


@login_required
@require_POST
def htmx_bank_random_select(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    preset_type, grade = _parse_bank_filters(
        request.POST.get("preset_type", DEFAULT_TOPIC),
        request.POST.get("grade", "all"),
    )
    scope = (request.POST.get("scope", "all") or "all").strip().lower()
    if scope not in {"official", "public", "all"}:
        scope = "all"

    banks_qs = _build_bank_queryset(
        classroom=classroom,
        user=request.user,
        preset_type=preset_type,
        grade=grade,
        scope=scope,
    )

    # 최근 7일 내 이미 사용한 은행 세트는 우선 제외
    recent_bank_ids = list(
        SQQuizSet.objects.filter(
            classroom=classroom,
            target_date__gte=timezone.localdate() - timedelta(days=7),
            bank_source__isnull=False,
        )
        .values_list("bank_source_id", flat=True)
        .distinct()
    )
    candidates = list(banks_qs.exclude(id__in=recent_bank_ids)[:100])
    if not candidates:
        candidates = list(banks_qs[:100])
    if not candidates:
        return HttpResponse(
            '<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            "랜덤으로 선택할 퀴즈 세트가 없습니다. 먼저 CSV 문제를 업로드해 주세요.</div>",
            status=404,
        )

    selected_bank = random.choice(candidates)
    try:
        quiz_set = copy_bank_to_draft(
            bank_id=selected_bank.id,
            classroom=classroom,
            teacher=request.user,
        )
    except ValueError as e:
        return HttpResponse(
            f'<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">{e}</div>',
            status=400,
        )

    items = quiz_set.items.order_by("order_no")
    return render(
        request,
        "seed_quiz/partials/teacher_preview.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "items": items,
            "rag_notice": f"랜덤 선택 완료: {selected_bank.get_preset_type_display()}",
        },
    )


@login_required
@require_POST
def htmx_bank_select(request, classroom_id, bank_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    try:
        quiz_set = copy_bank_to_draft(
            bank_id=bank_id,
            classroom=classroom,
            teacher=request.user,
        )
    except SQQuizBank.DoesNotExist:
        return HttpResponse(
            '<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            "선택한 퀴즈 세트를 찾을 수 없습니다.</div>",
            status=404,
        )
    except ValueError as e:
        return HttpResponse(
            f'<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">{e}</div>',
            status=400,
        )

    items = quiz_set.items.order_by("order_no")
    return render(
        request,
        "seed_quiz/partials/teacher_preview.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "items": items,
        },
    )


@login_required
@require_POST
def htmx_csv_upload(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    _clear_csv_error_report(request)
    csv_limits = _get_csv_upload_limits()
    csv_file = request.FILES.get("csv_file")
    if not csv_file:
        errors = ["CSV 파일을 선택해 주세요."]
        _log_csv_event(
            classroom=classroom,
            teacher=request.user,
            code="CSV_UPLOAD_PREVIEW_FAILED",
            level="warn",
            message="CSV 미리보기 실패: 파일 미선택",
            payload={"error_count": 1, "errors": _trim_errors(errors)},
        )
        token = _store_csv_error_report(request, ["CSV 파일을 선택해 주세요."])
        return render(
            request,
            "seed_quiz/partials/csv_upload_result.html",
            {
                "classroom": classroom,
                "created_count": 0,
                "errors": ["CSV 파일을 선택해 주세요."],
                "error_report_url": reverse(
                    "seed_quiz:download_csv_error_report",
                    kwargs={"classroom_id": classroom.id, "token": token},
                ),
            },
            status=400,
        )

    if int(getattr(csv_file, "size", 0) or 0) > csv_limits["max_file_bytes"]:
        errors = [
            "CSV 파일 용량이 제한을 초과했습니다. "
            f"(최대 {_humanize_bytes(csv_limits['max_file_bytes'])})"
        ]
        _log_csv_event(
            classroom=classroom,
            teacher=request.user,
            code="CSV_UPLOAD_PREVIEW_FAILED",
            level="warn",
            message="CSV 미리보기 실패: 파일 용량 초과",
            payload={
                "filename": getattr(csv_file, "name", ""),
                "file_size": int(getattr(csv_file, "size", 0) or 0),
                "error_count": len(errors),
                "errors": _trim_errors(errors),
            },
        )
        token = _store_csv_error_report(
            request,
            errors,
        )
        return render(
            request,
            "seed_quiz/partials/csv_upload_result.html",
            {
                "classroom": classroom,
                "created_count": 0,
                "updated_count": 0,
                "review_count": 0,
                "errors": [
                    "CSV 파일 용량이 제한을 초과했습니다. "
                    f"(최대 {_humanize_bytes(csv_limits['max_file_bytes'])})"
                ],
                "error_report_url": reverse(
                    "seed_quiz:download_csv_error_report",
                    kwargs={"classroom_id": classroom.id, "token": token},
                ),
            },
            status=400,
        )

    parsed_sets, errors = parse_csv_upload(
        csv_file,
        max_rows=csv_limits["max_rows"],
        max_sets=csv_limits["max_sets"],
    )
    if errors:
        _log_csv_event(
            classroom=classroom,
            teacher=request.user,
            code="CSV_UPLOAD_PREVIEW_FAILED",
            level="warn",
            message="CSV 미리보기 실패: 파싱/검증 오류",
            payload={
                "filename": getattr(csv_file, "name", ""),
                "file_size": int(getattr(csv_file, "size", 0) or 0),
                "error_count": len(errors),
                "errors": _trim_errors(errors),
            },
        )
        token = _store_csv_error_report(request, errors)
        return render(
            request,
            "seed_quiz/partials/csv_upload_result.html",
            {
                "classroom": classroom,
                "created_count": 0,
                "updated_count": 0,
                "review_count": 0,
                "errors": errors,
                "error_report_url": reverse(
                    "seed_quiz:download_csv_error_report",
                    kwargs={"classroom_id": classroom.id, "token": token},
                ),
            },
            status=400,
        )

    if not parsed_sets:
        errors = ["저장할 수 있는 문제 세트가 없습니다."]
        _log_csv_event(
            classroom=classroom,
            teacher=request.user,
            code="CSV_UPLOAD_PREVIEW_FAILED",
            level="warn",
            message="CSV 미리보기 실패: 유효 세트 없음",
            payload={
                "filename": getattr(csv_file, "name", ""),
                "file_size": int(getattr(csv_file, "size", 0) or 0),
                "error_count": len(errors),
                "errors": _trim_errors(errors),
            },
        )
        token = _store_csv_error_report(request, ["저장할 수 있는 문제 세트가 없습니다."])
        return render(
            request,
            "seed_quiz/partials/csv_upload_result.html",
            {
                "classroom": classroom,
                "created_count": 0,
                "updated_count": 0,
                "review_count": 0,
                "errors": ["저장할 수 있는 문제 세트가 없습니다."],
                "error_report_url": reverse(
                    "seed_quiz:download_csv_error_report",
                    kwargs={"classroom_id": classroom.id, "token": token},
                ),
            },
            status=400,
        )

    _log_csv_event(
        classroom=classroom,
        teacher=request.user,
        code="CSV_UPLOAD_PREVIEW_READY",
        level="info",
        message=f"CSV 미리보기 성공: {len(parsed_sets)}세트",
        payload={
            "filename": getattr(csv_file, "name", ""),
            "file_size": int(getattr(csv_file, "size", 0) or 0),
            "set_count": len(parsed_sets),
            "row_count": sum(len(s.get("items", [])) for s in parsed_sets),
        },
    )
    token = uuid4().hex
    request.session[CSV_PREVIEW_TOKEN_KEY] = token
    request.session[CSV_PREVIEW_PAYLOAD_KEY] = parsed_sets
    request.session.modified = True
    _clear_csv_error_report(request)

    return render(
        request,
        "seed_quiz/partials/csv_upload_preview.html",
        {
            "classroom": classroom,
            "preview_token": token,
            "parsed_sets": parsed_sets,
            "set_count": len(parsed_sets),
        },
    )


@login_required
@require_POST
def htmx_csv_confirm(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    token = (request.POST.get("preview_token") or "").strip()
    session_token = request.session.get(CSV_PREVIEW_TOKEN_KEY)
    parsed_sets = request.session.get(CSV_PREVIEW_PAYLOAD_KEY) or []

    if not token or token != session_token or not parsed_sets:
        _log_csv_event(
            classroom=classroom,
            teacher=request.user,
            code="CSV_UPLOAD_CONFIRM_FAILED",
            level="warn",
            message="CSV 저장 실패: 미리보기 세션 만료",
            payload={"error_count": 1, "errors": ["CSV 미리보기 세션이 만료되었습니다."]},
        )
        return render(
            request,
            "seed_quiz/partials/csv_upload_result.html",
            {
                "classroom": classroom,
                "created_count": 0,
                "updated_count": 0,
                "review_count": 0,
                "errors": ["CSV 미리보기 세션이 만료되었습니다. 다시 업로드해 주세요."],
            },
            status=400,
        )

    share_opt_in = (request.POST.get("share_opt_in") or "").lower() in {"on", "1", "true", "yes"}
    created_count, updated_count, review_count = save_parsed_sets_to_bank(
        parsed_sets=parsed_sets,
        created_by=request.user,
        share_opt_in=share_opt_in,
    )
    _log_csv_event(
        classroom=classroom,
        teacher=request.user,
        code="CSV_UPLOAD_CONFIRM_SUCCESS",
        level="info",
        message=f"CSV 저장 완료: 생성 {created_count}, 갱신 {updated_count}",
        payload={
            "set_count": len(parsed_sets),
            "created_count": created_count,
            "updated_count": updated_count,
            "review_count": review_count,
            "share_opt_in": bool(share_opt_in),
        },
    )

    request.session.pop(CSV_PREVIEW_TOKEN_KEY, None)
    request.session.pop(CSV_PREVIEW_PAYLOAD_KEY, None)
    request.session.modified = True

    return render(
        request,
        "seed_quiz/partials/csv_upload_result.html",
        {
            "classroom": classroom,
            "created_count": created_count,
            "updated_count": updated_count,
            "review_count": review_count,
            "errors": [],
        },
        status=200,
    )


@login_required
def htmx_csv_history(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    logs = (
        SQGenerationLog.objects.filter(
            code__in=[
                "CSV_UPLOAD_PREVIEW_READY",
                "CSV_UPLOAD_PREVIEW_FAILED",
                "CSV_UPLOAD_CONFIRM_SUCCESS",
                "CSV_UPLOAD_CONFIRM_FAILED",
            ],
            payload__classroom_id=str(classroom.id),
            payload__teacher_id=int(request.user.id),
        )
        .order_by("-created_at")[:20]
    )
    return render(
        request,
        "seed_quiz/partials/csv_upload_history.html",
        {"classroom": classroom, "history_logs": logs},
    )


@login_required
@require_POST
def htmx_rag_generate(request, classroom_id):
    if not bool(getattr(settings, "SEED_QUIZ_ALLOW_RAG", False)):
        return HttpResponse(
            '<div class="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">'
            "현재 맞춤 생성 기능이 비활성화되어 있습니다.</div>",
            status=403,
        )

    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    preset_type, grade = _parse_bank_filters(
        request.POST.get("preset_type", DEFAULT_TOPIC),
        request.POST.get("grade", "3"),
    )
    source_text = (request.POST.get("source_text") or "").strip()
    if not source_text:
        return HttpResponse(
            '<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            "지문 텍스트를 입력해 주세요.</div>",
            status=400,
        )

    daily_limit = max(0, int(getattr(settings, "SEED_QUIZ_RAG_DAILY_LIMIT", 1)))
    if daily_limit == 0:
        return HttpResponse(
            '<div class="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">'
            "현재 맞춤 생성 기능이 비활성화되어 있습니다.</div>",
            status=403,
        )

    allowed, remaining = consume_rag_quota(classroom=classroom, teacher=request.user, daily_limit=daily_limit)
    if not allowed:
        return HttpResponse(
            '<div class="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">'
            "오늘의 맞춤 생성 횟수를 모두 사용했습니다. 내일 다시 시도해 주세요.</div>",
            status=429,
        )

    try:
        result = generate_bank_from_context_ai(
            preset_type=preset_type,
            grade=grade,
            source_text=source_text,
            created_by=request.user,
        )
        if isinstance(result, tuple):
            bank, from_cache = result
        else:
            bank = result
            from_cache = False
        quiz_set = copy_bank_to_draft(bank_id=bank.id, classroom=classroom, teacher=request.user)
    except Exception as e:
        refund_rag_quota(classroom=classroom, teacher=request.user)
        return HttpResponse(
            f'<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            f"맞춤 생성 오류: {e}</div>",
            status=400,
        )

    items = quiz_set.items.order_by("order_no")
    return render(
        request,
        "seed_quiz/partials/teacher_preview.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "items": items,
            "rag_notice": (
                f"지문 기반 맞춤 생성 완료 (오늘 남은 횟수: {remaining})"
                if not from_cache
                else f"지문 기반 캐시 세트 재사용 (오늘 남은 횟수: {remaining})"
            ),
        },
    )


@login_required
@require_POST
def htmx_generate(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    preset_type, grade = _parse_bank_filters(
        request.POST.get("preset_type", DEFAULT_TOPIC),
        request.POST.get("grade", "3"),
    )

    try:
        quiz_set = generate_and_save_draft(classroom, preset_type, grade, request.user)
    except RuntimeError as e:
        return HttpResponse(
            f'<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            f"퀴즈 생성 오류: {e}</div>"
        )

    items = quiz_set.items.order_by("order_no")
    return render(
        request,
        "seed_quiz/partials/teacher_preview.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "items": items,
        },
    )


@login_required
@require_POST
def htmx_publish(request, classroom_id, set_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    quiz_set = get_object_or_404(
        SQQuizSet, id=set_id, classroom=classroom, status="draft"
    )
    force_replace = (request.POST.get("force_replace") or "").lower() in {"1", "true", "yes", "on"}
    existing_published = (
        SQQuizSet.objects.filter(
            classroom=classroom,
            target_date=quiz_set.target_date,
            preset_type=quiz_set.preset_type,
            status="published",
        )
        .exclude(id=quiz_set.id)
        .order_by("-published_at", "-updated_at")
        .first()
    )
    if existing_published and not force_replace:
        return render(
            request,
            "seed_quiz/partials/teacher_publish_confirm_replace.html",
            {
                "classroom": classroom,
                "quiz_set": quiz_set,
                "existing_published": existing_published,
            },
        )

    with transaction.atomic():
        replaced_set_id = None
        if existing_published:
            replaced_set_id = existing_published.id

        # 기존 published → closed
        SQQuizSet.objects.filter(
            classroom=classroom,
            target_date=quiz_set.target_date,
            preset_type=quiz_set.preset_type,
            status="published",
        ).exclude(id=quiz_set.id).update(status="closed")

        quiz_set.status = "published"
        quiz_set.published_at = timezone.now()
        quiz_set.published_by = request.user
        quiz_set.save(update_fields=["status", "published_at", "published_by"])
        if replaced_set_id:
            SQGenerationLog.objects.create(
                level="info",
                code="QUIZ_PUBLISH_REPLACED",
                message=f"퀴즈 재배포: {quiz_set.title}",
                payload={
                    "classroom_id": str(classroom.id),
                    "teacher_id": int(request.user.id),
                    "target_date": str(quiz_set.target_date),
                    "preset_type": quiz_set.preset_type,
                    "new_set_id": str(quiz_set.id),
                    "replaced_set_id": str(replaced_set_id),
                },
            )
        else:
            SQGenerationLog.objects.create(
                level="info",
                code="QUIZ_PUBLISH_NEW",
                message=f"퀴즈 배포: {quiz_set.title}",
                payload={
                    "classroom_id": str(classroom.id),
                    "teacher_id": int(request.user.id),
                    "target_date": str(quiz_set.target_date),
                    "preset_type": quiz_set.preset_type,
                    "new_set_id": str(quiz_set.id),
                },
            )

    student_url = request.build_absolute_uri(
        reverse(
            "seed_quiz:student_gate",
            kwargs={"class_slug": classroom.slug},
        )
    )
    return render(
        request,
        "seed_quiz/partials/teacher_published.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "student_url": student_url,
            "rollback_restore_set_id": str(replaced_set_id) if replaced_set_id else "",
            "rollback_from_set_id": str(quiz_set.id),
        },
    )


@login_required
@require_POST
def htmx_publish_rollback(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    restore_set_id = (request.POST.get("restore_set_id") or "").strip()
    current_set_id = (request.POST.get("current_set_id") or "").strip()
    if not restore_set_id:
        return HttpResponse(
            '<div class="p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">'
            "되돌릴 세트 정보가 없습니다.</div>",
            status=400,
        )

    restore_set = get_object_or_404(SQQuizSet, id=restore_set_id, classroom=classroom)

    with transaction.atomic():
        current_set = (
            SQQuizSet.objects.select_for_update()
            .filter(
                classroom=classroom,
                target_date=restore_set.target_date,
                preset_type=restore_set.preset_type,
                status="published",
            )
            .first()
        )
        if not current_set:
            return HttpResponse(
                '<div class="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">'
                "현재 배포 중인 세트를 찾을 수 없습니다. 이미 변경되었을 수 있습니다.</div>",
                status=409,
            )
        if current_set_id and str(current_set.id) != current_set_id:
            return HttpResponse(
                '<div class="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">'
                "배포 상태가 변경되어 되돌리기를 중단했습니다. 화면을 새로고침해 주세요.</div>",
                status=409,
            )
        if current_set.id == restore_set.id:
            return HttpResponse(
                '<div class="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">'
                "이미 해당 세트가 배포 중입니다.</div>",
                status=409,
            )

        SQQuizSet.objects.filter(id=current_set.id).update(status="closed")
        restore_set.status = "published"
        restore_set.published_at = timezone.now()
        restore_set.published_by = request.user
        restore_set.save(update_fields=["status", "published_at", "published_by"])

        SQGenerationLog.objects.create(
            level="info",
            code="QUIZ_PUBLISH_ROLLBACK",
            message=f"퀴즈 롤백: {restore_set.title}",
            payload={
                "classroom_id": str(classroom.id),
                "teacher_id": int(request.user.id),
                "target_date": str(restore_set.target_date),
                "preset_type": restore_set.preset_type,
                "restore_set_id": str(restore_set.id),
                "from_set_id": str(current_set.id),
            },
        )

    student_url = request.build_absolute_uri(
        reverse(
            "seed_quiz:student_gate",
            kwargs={"class_slug": classroom.slug},
        )
    )
    return render(
        request,
        "seed_quiz/partials/teacher_published.html",
        {
            "classroom": classroom,
            "quiz_set": restore_set,
            "student_url": student_url,
            "rollback_done": True,
        },
    )


@login_required
def htmx_progress(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    quiz_set = (
        SQQuizSet.objects.filter(
            classroom=classroom,
            target_date=timezone.localdate(),
            status="published",
        )
        .prefetch_related("attempts")
        .first()
    )

    stats = {}
    if quiz_set:
        total = classroom.students.filter(is_active=True).count()
        attempts = quiz_set.attempts.all()
        stats = {
            "total": total,
            "started": attempts.count(),
            "submitted": attempts.filter(status__in=["submitted", "rewarded"]).count(),
            "perfect": attempts.filter(score=3).count(),
        }
    return render(
        request,
        "seed_quiz/partials/teacher_progress.html",
        {
            "quiz_set": quiz_set,
            "stats": stats,
        },
    )


@login_required
def htmx_topic_summary(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    counts_by_topic = {
        row["preset_type"]: row
        for row in SQQuizBank.objects.filter(is_active=True)
        .values("preset_type")
        .annotate(
            total_count=Count("id"),
            official_count=Count("id", filter=Q(is_official=True)),
            public_count=Count("id", filter=Q(is_public=True)),
            review_count=Count("id", filter=Q(quality_status="review")),
            last_created=Max("created_at"),
        )
    }
    last_used_by_topic = {
        row["bank_source__preset_type"]: row["last_used"]
        for row in SQQuizSet.objects.filter(classroom=classroom, bank_source__isnull=False)
        .values("bank_source__preset_type")
        .annotate(last_used=Max("target_date"))
    }

    topics = []
    for topic_key, topic_label in SQQuizSet.PRESET_CHOICES:
        row = counts_by_topic.get(topic_key, {})
        topics.append(
            {
                "key": topic_key,
                "label": topic_label,
                "total_count": row.get("total_count", 0),
                "official_count": row.get("official_count", 0),
                "public_count": row.get("public_count", 0),
                "review_count": row.get("review_count", 0),
                "last_used": last_used_by_topic.get(topic_key),
            }
        )

    return render(
        request,
        "seed_quiz/partials/topic_summary.html",
        {
            "classroom": classroom,
            "topics": topics,
        },
    )


# ---------------------------------------------------------------------------
# 학생 뷰
# ---------------------------------------------------------------------------

def student_gate(request, class_slug):
    classroom = get_object_or_404(HSClassroom, slug=class_slug, is_active=True)
    quiz_set = get_today_published_set(classroom)
    error = request.session.pop("sq_gate_error", None)
    return render(
        request,
        "seed_quiz/student_gate.html",
        {
            "classroom": classroom,
            "quiz_set": quiz_set,
            "error": error,
        },
    )


@require_POST
def student_start(request, class_slug):
    classroom = get_object_or_404(HSClassroom, slug=class_slug, is_active=True)
    quiz_set = get_today_published_set(classroom)
    if not quiz_set:
        return redirect("seed_quiz:student_gate", class_slug=class_slug)

    number_raw = request.POST.get("number", "").strip()
    name = request.POST.get("name", "").strip()

    if not number_raw.isdigit() or not name:
        request.session["sq_gate_error"] = "번호와 이름을 모두 입력해 주세요."
        return redirect("seed_quiz:student_gate", class_slug=class_slug)

    student = HSStudent.objects.filter(
        classroom=classroom,
        number=int(number_raw),
        name=name,
        is_active=True,
    ).first()

    if not student:
        request.session["sq_gate_error"] = "번호와 이름을 다시 확인해 주세요."
        return redirect("seed_quiz:student_gate", class_slug=class_slug)

    attempt = find_or_create_attempt(quiz_set, student)
    set_session(request, classroom, student, attempt)

    if attempt.status in ("submitted", "rewarded"):
        return redirect("seed_quiz:htmx_play_result")

    return redirect("seed_quiz:student_play")


def student_play_shell(request):
    attempt_id = request.session.get("sq_attempt_id")
    if not attempt_id:
        return redirect("/")
    return render(request, "seed_quiz/student_play.html")


def htmx_play_current(request):
    attempt_id = request.session.get("sq_attempt_id")
    if not attempt_id:
        return HttpResponse(status=403)

    attempt = get_object_or_404(SQAttempt, id=attempt_id)

    if attempt.status in ("submitted", "rewarded"):
        return _render_result(request, attempt)

    item = get_current_item(attempt)
    if not item:
        # 모든 문항 답변됨 → 채점
        return _do_finish(request, attempt)

    answered_count = attempt.answers.count()
    return render(
        request,
        "seed_quiz/partials/play_item.html",
        {
            "item": item,
            "item_no": answered_count + 1,
            "total": 3,
        },
    )


@require_POST
def htmx_play_answer(request):
    attempt_id = request.session.get("sq_attempt_id")
    if not attempt_id:
        return HttpResponse(status=403)

    attempt = get_object_or_404(SQAttempt, id=attempt_id)

    if attempt.status in ("submitted", "rewarded"):
        return _render_result(request, attempt)

    item_id = request.POST.get("item_id")
    selected_raw = request.POST.get("selected_index", "")

    if not selected_raw.lstrip("-").isdigit():
        return HttpResponse(status=400)
    selected_index = int(selected_raw)
    if selected_index not in [0, 1, 2, 3]:
        return HttpResponse(status=400)

    # 해당 item이 현재 퀴즈 세트 소속이고, 현재 순서여야 함
    item = get_object_or_404(SQQuizItem, id=item_id, quiz_set=attempt.quiz_set)

    # 순서 검증: 현재 풀어야 할 문항만 허용
    expected_item = get_current_item(attempt)
    if expected_item is None or str(expected_item.id) != str(item.id):
        # 이미 완료되었거나 순서가 다름 → 현재 상태 기준으로 다음 화면 반환
        next_item = get_current_item(attempt)
        if next_item is None:
            return _do_finish(request, attempt)
        answered_count = attempt.answers.count()
        return render(
            request,
            "seed_quiz/partials/play_item.html",
            {"item": next_item, "item_no": answered_count + 1, "total": 3},
        )

    # 답변 저장 (이미 답변한 경우 get_or_create로 무시)
    SQAttempt.objects.select_for_update().filter(id=attempt.id)  # 잠금
    with transaction.atomic():
        attempt_locked = SQAttempt.objects.select_for_update().get(id=attempt.id)
        if attempt_locked.status in ("submitted", "rewarded"):
            return _render_result(request, attempt_locked)

        from seed_quiz.models import SQAttemptAnswer
        SQAttemptAnswer.objects.get_or_create(
            attempt=attempt_locked,
            item=item,
            defaults={
                "selected_index": selected_index,
                "is_correct": item.correct_index == selected_index,
            },
        )

    # 다음 문항 확인
    attempt.refresh_from_db()
    next_item = get_current_item(attempt)
    if next_item is None:
        return _do_finish(request, attempt)

    answered_count = attempt.answers.count()
    return render(
        request,
        "seed_quiz/partials/play_item.html",
        {"item": next_item, "item_no": answered_count + 1, "total": 3},
    )


def htmx_play_result(request):
    attempt_id = request.session.get("sq_attempt_id")
    if not attempt_id:
        return HttpResponse(status=403)
    attempt = get_object_or_404(SQAttempt, id=attempt_id)
    return _render_result(request, attempt)


def _do_finish(request, attempt: SQAttempt) -> HttpResponse:
    """채점 + 보상 처리 후 결과 partial 반환."""
    answers = {
        a.item.order_no: a.selected_index
        for a in attempt.answers.select_related("item").all()
    }
    attempt = submit_and_reward(attempt_id=attempt.id, answers=answers)
    return _render_result(request, attempt)


def _render_result(request, attempt: SQAttempt) -> HttpResponse:
    answers_by_order = {
        a.item.order_no: a
        for a in attempt.answers.select_related("item")
    }
    items_with_answers = []
    for item in attempt.quiz_set.items.order_by("order_no"):
        ans = answers_by_order.get(item.order_no)
        choices = item.choices or []
        selected_choice = choices[ans.selected_index] if ans and 0 <= ans.selected_index < len(choices) else ""
        items_with_answers.append({
            "item": item,
            "answer": ans,
            "correct_choice": choices[item.correct_index] if 0 <= item.correct_index < len(choices) else "",
            "selected_choice": selected_choice,
        })
    return render(
        request,
        "seed_quiz/partials/play_result.html",
        {
            "attempt": attempt,
            "items_with_answers": items_with_answers,
        },
    )
