import logging
import uuid
import csv
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_date

from products.models import Product

from .forms import TimetableUploadForm
from .models import TimetableSyncLog
from .services import (
    REQUIRED_SHEETS,
    apply_schedule_to_reservations,
    build_template_workbook,
    generate_timetable_schedule,
    validate_timetable_workbook,
)

logger = logging.getLogger(__name__)

SERVICE_TITLE = "전담 시간표·특별실 배치 도우미"
SYNC_SESSION_KEY = "timetable_sync_payload"


def _get_service():
    service = Product.objects.filter(launch_route_name="timetable:main").first()
    if service:
        return service
    return Product.objects.filter(title=SERVICE_TITLE).first()


def main(request):
    school_choices, school_map = _get_school_choices(request)
    log_filters = _get_sync_log_filters(request)
    action = (request.POST.get("action") or "generate").strip() if request.method == "POST" else ""
    form = TimetableUploadForm(
        request.POST if request.method == "POST" and action == "generate" else None,
        request.FILES if request.method == "POST" and action == "generate" else None,
        school_choices=school_choices,
    )
    check_result = None
    generated_result = None
    integration_result = None
    preview_apply_info = None

    if request.method == "POST":
        if action == "apply_preview":
            integration_result, preview_apply_info = _apply_preview_sync(request, school_map)
            _attach_reservation_links(integration_result)
            if integration_result:
                _record_sync_log(
                    request,
                    integration_result=integration_result,
                    sync_mode="preview_manual",
                    sync_options={"미리보기"},
                    overwrite_existing=bool(integration_result.get("overwrite_existing")),
                )
        elif form.is_valid():
            file_obj = form.cleaned_data["excel_file"]
            selected_school_slug = form.cleaned_data.get("reservation_school_slug") or ""
            overwrite_requested = bool(form.cleaned_data.get("overwrite_existing"))
            check_result = validate_timetable_workbook(file_obj)
            if check_result["is_valid"]:
                generated_result = generate_timetable_schedule(file_obj)
                if generated_result["is_success"]:
                    preview_apply_info = _save_sync_payload(
                        request,
                        generated_result=generated_result,
                        school_slug=selected_school_slug,
                    )
                    if selected_school_slug:
                        school = school_map.get(selected_school_slug)
                        if school:
                            can_overwrite = _can_use_overwrite_option(request, school)
                            overwrite_existing = overwrite_requested and can_overwrite
                            if overwrite_requested and not can_overwrite:
                                messages.warning(request, "덮어쓰기는 해당 학교 관리자만 사용할 수 있습니다.")
                            integration_result = apply_schedule_to_reservations(
                                generated_result,
                                school=school,
                                overwrite_existing=overwrite_existing,
                                sync_options={"바로반영"},
                            )
                            integration_result["overwrite_existing"] = overwrite_existing
                            _attach_reservation_links(integration_result)
                            _record_sync_log(
                                request,
                                integration_result=integration_result,
                                sync_mode="direct",
                                sync_options={"바로반영"},
                                overwrite_existing=overwrite_existing,
                            )
                        else:
                            messages.warning(request, "선택한 학교 정보를 찾지 못해 예약 반영을 건너뛰었습니다.")
                    messages.success(request, "입력 점검과 전담 자동 배치가 완료되었습니다.")
                    logger.info("[Timetable] Action: AUTO_SCHEDULE, Status: SUCCESS")
                else:
                    messages.warning(request, "입력은 올바르지만 자동 배치에서 수정이 필요한 항목이 있습니다.")
                    logger.info("[Timetable] Action: AUTO_SCHEDULE, Status: PARTIAL")
            else:
                messages.error(request, "입력 양식에 수정이 필요한 항목이 있습니다. 점검 결과를 확인해 주세요.")
                logger.info("[Timetable] Action: TEMPLATE_CHECK, Status: FAIL")
        else:
            messages.error(request, "엑셀 파일을 선택해 주세요.")

    context = {
        "service": _get_service(),
        "form": form,
        "check_result": check_result,
        "generated_result": generated_result,
        "integration_result": integration_result,
        "preview_apply_info": preview_apply_info,
        "can_use_overwrite_option": request.user.is_authenticated and bool(school_choices),
        "required_sheet_names": list(REQUIRED_SHEETS.keys()),
        "recent_sync_logs": _get_recent_sync_logs(request, log_filters=log_filters),
        "log_filters": log_filters,
        "log_school_options": _get_sync_log_school_options(request, log_filters=log_filters),
        "csv_download_query": _build_sync_log_filter_query(log_filters),
    }
    return render(request, "timetable/main.html", context)


@login_required
def download_sync_logs_csv(request):
    log_filters = _get_sync_log_filters(request)
    logs = _get_sync_log_queryset(request, log_filters=log_filters)

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="예약반영내역.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "실행시각",
            "실행자",
            "학교슬러그",
            "학교명",
            "반영방식",
            "반영옵션",
            "덮어쓰기",
            "결과",
            "새로반영",
            "이름갱신",
            "건너뜀",
            "기존값충돌",
            "신규특별실",
            "요약",
        ]
    )

    for row in logs:
        writer.writerow(
            [
                row.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                row.user.username if row.user else "",
                row.school_slug,
                row.school_name,
                row.get_sync_mode_display(),
                row.sync_options_text,
                "Y" if row.overwrite_existing else "N",
                row.get_status_display(),
                row.applied_count,
                row.updated_count,
                row.skipped_count,
                row.conflict_count,
                row.room_created_count,
                row.summary_text,
            ]
        )

    return response


def download_template(request):
    file_data = build_template_workbook()
    response = HttpResponse(
        file_data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="timetable_input_template_v1.xlsx"'
    return response


def _get_school_choices(request):
    if not request.user.is_authenticated:
        return [], {}

    try:
        from reservations.models import School
    except Exception:
        return [], {}

    schools = list(School.objects.filter(owner=request.user).order_by("name"))
    choices = [(school.slug, school.name) for school in schools]
    school_map = {school.slug: school for school in schools}
    return choices, school_map


def _save_sync_payload(request, generated_result, school_slug):
    if not school_slug:
        request.session.pop(SYNC_SESSION_KEY, None)
        request.session.modified = True
        return None

    preview_items = [
        item for item in generated_result.get("sync_candidates", []) if item.get("sync_option") == "미리보기"
    ]
    if not preview_items:
        request.session.pop(SYNC_SESSION_KEY, None)
        request.session.modified = True
        return None

    token = uuid.uuid4().hex
    payload = {
        "token": token,
        "school_slug": school_slug,
        "days": generated_result.get("days", []),
        "slot_labels": generated_result.get("slot_labels", []),
        "sync_candidates": generated_result.get("sync_candidates", []),
    }
    request.session[SYNC_SESSION_KEY] = payload
    request.session.modified = True
    return {
        "token": token,
        "school_slug": school_slug,
        "preview_count": len(preview_items),
        "school_name": None,
    }


def _apply_preview_sync(request, school_map):
    token = (request.POST.get("sync_token") or "").strip()
    school_slug = (request.POST.get("school_slug") or "").strip()
    overwrite_requested = (request.POST.get("overwrite_existing") or "").lower() in {"on", "true", "1", "yes"}
    cached = request.session.get(SYNC_SESSION_KEY) or {}

    if not token or not school_slug:
        messages.error(request, "미리보기 반영 정보를 찾지 못했습니다. 파일 업로드부터 다시 진행해 주세요.")
        return None, None
    if cached.get("token") != token or cached.get("school_slug") != school_slug:
        messages.error(request, "미리보기 반영 정보가 만료되었거나 일치하지 않습니다. 다시 업로드해 주세요.")
        return None, None

    school = school_map.get(school_slug)
    if not school:
        messages.error(request, "선택한 학교 정보를 찾지 못했습니다.")
        return None, None

    can_overwrite = _can_use_overwrite_option(request, school)
    overwrite_existing = overwrite_requested and can_overwrite
    if overwrite_requested and not can_overwrite:
        messages.warning(request, "덮어쓰기는 해당 학교 관리자만 사용할 수 있습니다.")

    generated_payload = {
        "days": cached.get("days", []),
        "slot_labels": cached.get("slot_labels", []),
        "sync_candidates": cached.get("sync_candidates", []),
    }
    integration_result = apply_schedule_to_reservations(
        generated_payload,
        school=school,
        overwrite_existing=overwrite_existing,
        sync_options={"미리보기"},
    )
    integration_result["is_manual_preview"] = True
    integration_result["overwrite_existing"] = overwrite_existing
    messages.success(request, "미리보기 항목을 예약 시스템에 반영했습니다.")

    preview_count = len(
        [item for item in cached.get("sync_candidates", []) if item.get("sync_option") == "미리보기"]
    )
    return integration_result, {
        "token": token,
        "school_slug": school_slug,
        "preview_count": preview_count,
        "school_name": school.name,
    }


def _can_use_overwrite_option(request, school):
    if not request.user.is_authenticated:
        return False
    return request.user.is_superuser or school.owner_id == request.user.id


def _attach_reservation_links(integration_result):
    if not integration_result:
        return
    school_slug = integration_result.get("school_slug")
    if not school_slug:
        return
    integration_result["reservation_url"] = reverse(
        "reservations:reservation_index", kwargs={"school_slug": school_slug}
    )
    integration_result["reservation_admin_url"] = reverse(
        "reservations:admin_dashboard", kwargs={"school_slug": school_slug}
    )


def _record_sync_log(request, integration_result, sync_mode, sync_options, overwrite_existing):
    if not integration_result:
        return

    sync_options_text = ",".join(sorted(sync_options)) if sync_options else ""
    summary_parts = [
        f"새로 반영 {integration_result.get('applied_count', 0)}건",
        f"이름 갱신 {integration_result.get('updated_count', 0)}건",
        f"건너뜀 {integration_result.get('skipped_count', 0)}건",
    ]
    if integration_result.get("conflict_count", 0):
        summary_parts.append(f"기존값 충돌 {integration_result.get('conflict_count')}건")
    if overwrite_existing:
        summary_parts.append("덮어쓰기 사용")

    TimetableSyncLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        school_slug=integration_result.get("school_slug", ""),
        school_name=integration_result.get("school_name", ""),
        sync_mode=sync_mode,
        sync_options_text=sync_options_text,
        overwrite_existing=overwrite_existing,
        status=integration_result.get("status", "success"),
        applied_count=integration_result.get("applied_count", 0),
        updated_count=integration_result.get("updated_count", 0),
        skipped_count=integration_result.get("skipped_count", 0),
        conflict_count=integration_result.get("conflict_count", 0),
        room_created_count=integration_result.get("room_created_count", 0),
        summary_text=" | ".join(summary_parts),
        payload={
            "messages": integration_result.get("messages", []),
            "reservation_url": integration_result.get("reservation_url", ""),
            "reservation_admin_url": integration_result.get("reservation_admin_url", ""),
        },
    )


def _get_recent_sync_logs(request, log_filters=None):
    if not request.user.is_authenticated:
        return []
    return list(_get_sync_log_queryset(request, log_filters=log_filters)[:15])


def _get_sync_log_queryset(request, log_filters=None):
    qs = _get_sync_log_base_queryset(request)
    if log_filters:
        qs = _apply_sync_log_filters(qs, log_filters)
    return qs


def _get_sync_log_base_queryset(request):
    if not request.user.is_authenticated:
        return TimetableSyncLog.objects.none()

    qs = TimetableSyncLog.objects.select_related("user").order_by("-created_at")
    if request.user.is_superuser:
        return qs
    return qs.filter(user=request.user)


def _get_sync_log_filters(request):
    school_slug = (request.GET.get("log_school_slug") or "").strip()
    date_from_raw = (request.GET.get("log_date_from") or "").strip()
    date_to_raw = (request.GET.get("log_date_to") or "").strip()

    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None

    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    return {
        "school_slug": school_slug,
        "date_from": date_from,
        "date_to": date_to,
        "date_from_text": date_from.isoformat() if date_from else "",
        "date_to_text": date_to.isoformat() if date_to else "",
    }


def _apply_sync_log_filters(qs, log_filters):
    school_slug = (log_filters or {}).get("school_slug") or ""
    date_from = (log_filters or {}).get("date_from")
    date_to = (log_filters or {}).get("date_to")

    if school_slug:
        qs = qs.filter(school_slug=school_slug)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    return qs


def _get_sync_log_school_options(request, log_filters=None):
    if not request.user.is_authenticated:
        return []

    if request.user.is_superuser:
        raw_rows = TimetableSyncLog.objects.exclude(school_slug="").values_list("school_slug", "school_name")
    else:
        raw_rows = TimetableSyncLog.objects.filter(user=request.user).exclude(school_slug="").values_list(
            "school_slug",
            "school_name",
        )

    school_map = {}
    for school_slug, school_name in raw_rows:
        if school_slug not in school_map or (not school_map[school_slug] and school_name):
            school_map[school_slug] = school_name

    selected_school_slug = (log_filters or {}).get("school_slug") or ""
    if selected_school_slug and selected_school_slug not in school_map:
        school_map[selected_school_slug] = selected_school_slug

    options = [(slug, name or slug) for slug, name in school_map.items()]
    return sorted(options, key=lambda item: item[1])


def _build_sync_log_filter_query(log_filters):
    if not log_filters:
        return ""

    params = {}
    if log_filters.get("school_slug"):
        params["log_school_slug"] = log_filters["school_slug"]
    if log_filters.get("date_from_text"):
        params["log_date_from"] = log_filters["date_from_text"]
    if log_filters.get("date_to_text"):
        params["log_date_to"] = log_filters["date_to_text"]
    return urlencode(params)
