from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from edu_materials.models import EduMaterial
from edu_materials.ai_limits import auto_metadata_limit_exceeded

from .classification import (
    apply_auto_metadata,
    apply_manual_metadata,
    build_search_text,
)
from .learning_paths import (
    MISSION_LIBRARY,
    STARTER_LIBRARY,
    TOPIC_PLACEHOLDER,
    build_ai_prompt,
    get_mission,
    get_starter,
)
from .models import NextEduMaterial
from .runtime import build_runtime_data_url, build_runtime_html
from .services import build_material_qr_data_url, get_service, validate_html_upload


PREVIEW_VIEWPORTS = (
    {"id": "desktop", "label": "Desktop", "width": 1280, "height": 720},
    {"id": "mobile", "label": "Mobile", "width": 390, "height": 844},
)
DEFAULT_PREVIEW_VIEWPORT_ID = "desktop"
MY_PAGE_SIZE = 8
LEGACY_PAGE_SIZE = 6


def _resolve_teacher_display_name(user):
    if not user:
        return "익명의 선생님"

    nickname = ""
    try:
        nickname = (user.userprofile.nickname or "").strip()
    except Exception:
        nickname = ""

    if nickname:
        return nickname

    username = (getattr(user, "username", "") or "").strip()
    return username or "익명의 선생님"


def _build_preview_context():
    preview_viewports = [dict(viewport) for viewport in PREVIEW_VIEWPORTS]
    preview_default_viewport = next(
        viewport for viewport in preview_viewports if viewport["id"] == DEFAULT_PREVIEW_VIEWPORT_ID
    )
    return {
        "preview_viewports": preview_viewports,
        "preview_default_viewport": preview_default_viewport,
    }


def _append_csp_update(response, updates):
    current = dict(getattr(response, "_csp_update", {}) or {})
    for directive, sources in updates.items():
        merged_sources = list(current.get(directive, ()) or ())
        for source in sources:
            if source not in merged_sources:
                merged_sources.append(source)
        current[directive] = tuple(merged_sources)
    response._csp_update = current
    return response


def _build_query_string(request, *, exclude=()):
    params = request.GET.copy()
    for key in exclude:
        params.pop(key, None)
    return params.urlencode()


def _apply_auto_metadata_with_feedback(request, material):
    if auto_metadata_limit_exceeded(request.user, material=material):
        messages.warning(request, "오늘 자동 분류 한도를 모두 사용했습니다. 제목과 요약만 확인해 주세요.")
        return None
    metadata = apply_auto_metadata(material, save=True)
    if metadata is None:
        messages.warning(request, "자료는 저장했지만 분류는 잠시 비워 두었습니다. 제목과 요약만 확인하고 바로 써도 됩니다.")
    return metadata


def _build_share_message(*, material, join_url):
    return "\n".join(
        [
            f"[{material.title}]",
            f"학생 입력 주소: {join_url}",
            f"공유 코드: {material.access_code}",
            "QR을 스캔하거나 숫자 코드를 입력해 자료를 여세요.",
        ]
    )


def _build_import_questions(material):
    base = material.summary.strip() if material.summary else material.title.strip()
    return [
        f"{base}에서 학생이 가장 먼저 볼 핵심 장면은 무엇인가요?",
        "학생이 직접 바꿔 보게 할 값이나 버튼은 무엇인가요?",
        "수업 마무리 질문 하나를 추가한다면 무엇이 좋을까요?",
    ]


def _build_import_tips(material):
    return [
        "첫 화면 제목을 내 수업 주제에 맞게 바꾸기",
        "버튼 수를 줄여 학생이 바로 눌러 보게 만들기",
        "수업 끝 질문 1개를 화면 아래에 추가하기",
    ]


def _serialize_starter_for_template(starter):
    if not starter:
        return None
    return dict(starter)


def main_view(request):
    starter_slug = (request.GET.get("starter") or "").strip()
    mission_slug = (request.GET.get("mission") or "").strip()
    material_query = (request.GET.get("q") or "").strip()
    legacy_query = (request.GET.get("legacy_q") or "").strip()
    topic_seed = (request.GET.get("topic") or "").strip()

    selected_mission = get_mission(mission_slug) if mission_slug else None
    selected_starter = get_starter(starter_slug) if starter_slug else None
    if not selected_mission and not selected_starter and MISSION_LIBRARY:
        selected_mission = get_mission(MISSION_LIBRARY[0]["slug"])
    if not selected_starter and selected_mission:
        selected_starter = get_starter(selected_mission["starter_slug"])

    starters = [_serialize_starter_for_template(starter) for starter in STARTER_LIBRARY]
    missions = list(MISSION_LIBRARY)
    if selected_starter:
        generated_prompt_template = build_ai_prompt("", starter=selected_starter, mission=selected_mission)
        generated_prompt = build_ai_prompt(topic_seed, starter=selected_starter, mission=selected_mission)
    else:
        generated_prompt_template = build_ai_prompt("", mission=selected_mission)
        generated_prompt = build_ai_prompt(topic_seed, mission=selected_mission)

    my_page_obj = None
    legacy_page_obj = None
    my_material_count = 0
    legacy_material_count = 0
    if request.user.is_authenticated:
        my_queryset = NextEduMaterial.objects.filter(teacher=request.user)
        if material_query:
            my_queryset = my_queryset.filter(
                Q(title__icontains=material_query)
                | Q(summary__icontains=material_query)
                | Q(unit_title__icontains=material_query)
                | Q(search_text__icontains=material_query)
            )
        my_queryset = my_queryset.order_by("-updated_at", "-created_at")
        my_material_count = my_queryset.count()
        my_page_obj = Paginator(my_queryset, MY_PAGE_SIZE).get_page(request.GET.get("my_page"))

        legacy_queryset = EduMaterial.objects.filter(teacher=request.user)
        if legacy_query:
            legacy_queryset = legacy_queryset.filter(
                Q(title__icontains=legacy_query)
                | Q(summary__icontains=legacy_query)
                | Q(unit_title__icontains=legacy_query)
                | Q(search_text__icontains=legacy_query)
            )
        legacy_queryset = legacy_queryset.order_by("-updated_at", "-created_at")
        legacy_material_count = legacy_queryset.count()
        legacy_page_obj = Paginator(legacy_queryset, LEGACY_PAGE_SIZE).get_page(request.GET.get("legacy_page"))

    return render(
        request,
        "edu_materials_next/main.html",
        {
            "service": get_service(),
            "starters": starters,
            "missions": missions,
            "selected_starter": _serialize_starter_for_template(selected_starter),
            "selected_mission": selected_mission,
            "generated_prompt": generated_prompt,
            "generated_prompt_template": generated_prompt_template,
            "prompt_topic_placeholder": TOPIC_PLACEHOLDER,
            "topic_seed": topic_seed,
            "material_query": material_query,
            "legacy_query": legacy_query,
            "my_page_obj": my_page_obj,
            "legacy_page_obj": legacy_page_obj,
            "my_material_count": my_material_count,
            "legacy_material_count": legacy_material_count,
            "my_page_query_string": _build_query_string(request, exclude=("my_page",)),
            "legacy_page_query_string": _build_query_string(request, exclude=("legacy_page",)),
        },
    )


@login_required
@require_POST
def create_material(request):
    title = (request.POST.get("title") or "").strip()
    html_content = request.POST.get("html_content", "")
    topic = (request.POST.get("lesson_topic") or "").strip()
    starter_slug = (request.POST.get("starter_slug") or "").strip()
    starter = get_starter(starter_slug) if starter_slug else None

    if not title:
        messages.error(request, "자료 제목을 먼저 적어 주세요.")
        return redirect(f"{reverse('edu_materials_next:main')}#learn")

    uploaded_file = request.FILES.get("html_file")
    original_filename = ""
    entry_mode = NextEduMaterial.EntryMode.PASTE
    if starter and topic:
        entry_mode = NextEduMaterial.EntryMode.LEARN
    elif starter:
        entry_mode = NextEduMaterial.EntryMode.STARTER

    if uploaded_file:
        try:
            metadata = validate_html_upload(uploaded_file)
        except Exception as exc:
            messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
            return redirect(f"{reverse('edu_materials_next:main')}#learn")
        html_content = metadata["html_content"]
        original_filename = metadata["original_filename"]
        if not starter:
            entry_mode = NextEduMaterial.EntryMode.FILE
    elif not html_content.strip():
        messages.error(request, "완성된 HTML을 붙여넣거나 파일을 올려 주세요.")
        return redirect(f"{reverse('edu_materials_next:main')}#learn")

    material = NextEduMaterial.objects.create(
        teacher=request.user,
        title=title,
        html_content=html_content,
        entry_mode=entry_mode,
        original_filename=original_filename,
        teacher_guide=(starter or {}).get("teacher_guide", ""),
        student_questions=list((starter or {}).get("student_questions", [])),
        remix_tips=list((starter or {}).get("remix_tips", [])),
        estimated_minutes=(starter or {}).get("estimated_minutes", 15),
        difficulty_level=(starter or {}).get("difficulty_level", NextEduMaterial.DifficultyLevel.BEGINNER),
        is_published=True,
    )
    if starter:
        apply_manual_metadata(
            material,
            subject=starter["subject"],
            grade=starter["grade"],
            unit_title=starter["unit_title"],
            material_type=starter["material_type"],
            tags=[starter["title"], topic or starter["subject"]],
            summary=starter["summary"],
            save=True,
        )
    else:
        _apply_auto_metadata_with_feedback(request, material)

    messages.success(request, f'"{material.title}" 자료를 저장했고 바로 QR 배포 준비까지 마쳤습니다.')
    return redirect("edu_materials_next:detail", pk=material.id)


@login_required
@require_POST
def import_legacy_material(request, legacy_uuid):
    legacy_material = get_object_or_404(EduMaterial.objects.select_related("teacher"), id=legacy_uuid)
    if legacy_material.teacher_id != request.user.id and not legacy_material.is_published:
        raise Http404()

    existing = NextEduMaterial.objects.filter(
        teacher=request.user,
        legacy_source_material_id=legacy_material.id,
    ).first()
    if existing:
        messages.info(request, f'"{legacy_material.title}" 자료는 이미 Next에 가져왔습니다. 그 자료를 바로 열었습니다.')
        return redirect("edu_materials_next:detail", pk=existing.id)

    imported = NextEduMaterial.objects.create(
        teacher=request.user,
        title=f"{legacy_material.title} (Next)",
        html_content=legacy_material.html_content,
        access_code=None,
        is_published=True,
        subject=legacy_material.subject,
        grade=legacy_material.grade,
        unit_title=legacy_material.unit_title,
        material_type=legacy_material.material_type,
        summary=legacy_material.summary,
        tags=list(legacy_material.tags or []),
        search_text=legacy_material.search_text,
        entry_mode=NextEduMaterial.EntryMode.IMPORT,
        original_filename=legacy_material.original_filename,
        teacher_guide=legacy_material.summary or "기존 자료를 Next 흐름에 맞게 다듬어 바로 배포해 보세요.",
        student_questions=_build_import_questions(legacy_material),
        remix_tips=_build_import_tips(legacy_material),
        estimated_minutes=15,
        difficulty_level=NextEduMaterial.DifficultyLevel.BEGINNER,
        legacy_source_material_id=legacy_material.id,
    )
    imported.search_text = build_search_text(imported)
    imported.save(update_fields=["search_text", "updated_at"])
    messages.success(request, f'"{legacy_material.title}" 자료를 Next 버전으로 복사해 왔습니다.')
    return redirect("edu_materials_next:detail", pk=imported.id)


@login_required
@require_POST
def update_material(request, material_id):
    material = get_object_or_404(NextEduMaterial, id=material_id, teacher=request.user)
    title = (request.POST.get("title") or "").strip()
    html_content = request.POST.get("html_content", "")

    if not title:
        messages.error(request, "자료 제목을 먼저 적어 주세요.")
        return redirect("edu_materials_next:detail", pk=material.id)

    uploaded_file = request.FILES.get("html_file")
    if uploaded_file:
        try:
            metadata = validate_html_upload(uploaded_file)
        except Exception as exc:
            messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
            return redirect("edu_materials_next:detail", pk=material.id)
        material.html_content = metadata["html_content"]
        material.original_filename = metadata["original_filename"]
        material.entry_mode = NextEduMaterial.EntryMode.FILE
    elif html_content.strip():
        material.html_content = html_content
        material.original_filename = ""
        if material.entry_mode != NextEduMaterial.EntryMode.IMPORT:
            material.entry_mode = NextEduMaterial.EntryMode.PASTE
    else:
        messages.error(request, "바꿀 HTML 내용을 붙여넣거나 새 파일을 올려 주세요.")
        return redirect("edu_materials_next:detail", pk=material.id)

    material.title = title
    material.teacher_guide = (request.POST.get("teacher_guide") or "").strip()
    material.summary = (request.POST.get("summary") or material.summary or "").strip()[:120]
    material.reflection_note = (request.POST.get("reflection_note") or "").strip()
    material.search_text = build_search_text(material)
    material.save()
    messages.success(request, f'"{material.title}" 자료를 수정했습니다.')
    return redirect("edu_materials_next:detail", pk=material.id)


@login_required
@require_POST
def delete_material(request, material_id):
    material = get_object_or_404(NextEduMaterial, id=material_id, teacher=request.user)
    title = material.title
    material.delete()
    messages.success(request, f'"{title}" 자료를 삭제했습니다.')
    return redirect("edu_materials_next:main")


def material_detail(request, pk):
    material = get_object_or_404(NextEduMaterial.objects.select_related("teacher"), id=pk)
    is_owner = request.user.is_authenticated and material.teacher_id == request.user.id
    if not is_owner and not material.is_published:
        raise Http404()

    public_url = request.build_absolute_uri(reverse("edu_materials_next:run", args=[material.id]))
    student_join_url = request.build_absolute_uri(reverse("edu_materials_next:join_short"))
    student_join_display = f"{request.get_host()}{reverse('edu_materials_next:join_short')}"
    material_render_url = reverse("edu_materials_next:render", args=[material.id])
    response = render(
        request,
        "edu_materials_next/detail.html",
        {
            "service": get_service(),
            "material": material,
            "is_owner": is_owner,
            "teacher_display_name": _resolve_teacher_display_name(material.teacher),
            "material_frame_src": build_runtime_data_url(material.html_content),
            "material_render_url": material_render_url,
            "student_join_url": student_join_url,
            "student_join_display": student_join_display,
            "share_board_url": reverse("edu_materials_next:share_board", args=[material.id]),
            "public_qr_data_url": build_material_qr_data_url(public_url),
            "share_message": _build_share_message(material=material, join_url=student_join_url),
            **_build_preview_context(),
        },
    )
    return _append_csp_update(response, {"frame-src": ("data:",)})


def join_material(request):
    submitted_code = (request.GET.get("code") or "").strip()
    normalized_code = "".join(character for character in submitted_code if character.isdigit())
    error_message = ""

    if submitted_code:
        if len(normalized_code) != 6:
            error_message = "공유 코드는 숫자 6자리로 입력해 주세요."
        else:
            material = NextEduMaterial.objects.filter(access_code=normalized_code, is_published=True).first()
            if material:
                return redirect("edu_materials_next:run", pk=material.id)
            error_message = "입력한 공유 코드를 찾지 못했습니다. 선생님이 보여준 6자리 숫자를 다시 확인해 주세요."

    return render(
        request,
        "edu_materials_next/join.html",
        {
            "service": get_service(),
            "submitted_code": normalized_code,
            "error_message": error_message,
        },
    )


def share_board(request, pk):
    material = get_object_or_404(NextEduMaterial.objects.select_related("teacher"), id=pk)
    is_owner = request.user.is_authenticated and material.teacher_id == request.user.id
    if not material.is_published and not is_owner:
        raise Http404()

    student_join_display = f"{request.get_host()}{reverse('edu_materials_next:join_short')}"
    public_url = request.build_absolute_uri(reverse("edu_materials_next:run", args=[material.id]))
    return render(
        request,
        "edu_materials_next/share_board.html",
        {
            "material": material,
            "hide_navbar": True,
            "is_owner": is_owner,
            "teacher_display_name": _resolve_teacher_display_name(material.teacher),
            "student_join_display": student_join_display,
            "public_qr_data_url": build_material_qr_data_url(public_url),
        },
    )


def run_material(request, pk):
    material = get_object_or_404(NextEduMaterial, id=pk)
    if not material.is_published:
        raise Http404()
    NextEduMaterial.objects.filter(id=material.id).update(view_count=F("view_count") + 1)
    material.refresh_from_db(fields=["view_count"])
    response = render(
        request,
        "edu_materials_next/run.html",
        {
            "material": material,
            "hide_navbar": True,
            "material_frame_src": build_runtime_data_url(material.html_content),
            "material_render_url": reverse("edu_materials_next:render", args=[material.id]),
            **_build_preview_context(),
        },
    )
    return _append_csp_update(response, {"frame-src": ("data:",)})


def render_material(request, pk):
    material = get_object_or_404(NextEduMaterial, id=pk)
    is_teacher_preview = request.user.is_authenticated and material.teacher_id == request.user.id
    if not material.is_published and not is_teacher_preview:
        raise Http404()

    response = HttpResponse(build_runtime_html(material.html_content), content_type="text/html; charset=utf-8")
    response["Content-Security-Policy"] = (
        "sandbox allow-downloads allow-forms allow-modals allow-pointer-lock "
        "allow-popups allow-popups-to-escape-sandbox allow-presentation allow-scripts; "
        "frame-ancestors 'self';"
    )
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response
