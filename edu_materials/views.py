from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .classification import apply_auto_metadata, apply_manual_metadata, collect_popular_tags, parse_tags_input
from .models import EduMaterial
from .services import build_material_qr_data_url, get_service, validate_html_upload


PREVIEW_VIEWPORTS = (
    {"id": "desktop", "label": "Desktop", "width": 1280, "height": 720},
    {"id": "mobile", "label": "Mobile", "width": 390, "height": 844},
)
DEFAULT_PREVIEW_VIEWPORT_ID = "desktop"


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
        viewport
        for viewport in preview_viewports
        if viewport["id"] == DEFAULT_PREVIEW_VIEWPORT_ID
    )
    return {
        "preview_viewports": preview_viewports,
        "preview_default_viewport": preview_default_viewport,
    }


def _apply_metadata_filter(queryset, *, query="", subject="", material_type="", grade="", tag=""):
    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(unit_title__icontains=query)
            | Q(search_text__icontains=query)
        )
    if subject:
        queryset = queryset.filter(subject=subject)
    if material_type:
        queryset = queryset.filter(material_type=material_type)
    if grade:
        queryset = queryset.filter(grade=grade)
    if tag:
        queryset = queryset.filter(search_text__icontains=tag)
    return queryset


def _build_filter_context(request):
    query = (request.GET.get("q") or "").strip()
    subject = (request.GET.get("subject") or "").strip().upper()
    material_type = (request.GET.get("material_type") or "").strip().lower()
    grade = (request.GET.get("grade") or "").strip()
    tag = (request.GET.get("tag") or "").strip()

    accessible = EduMaterial.objects.filter(Q(teacher=request.user) | Q(is_published=True)).distinct()
    grade_options = list(
        accessible.exclude(grade="")
        .values_list("grade", flat=True)
        .order_by("grade")
        .distinct()
    )
    popular_tags = collect_popular_tags(accessible)

    return {
        "query": query,
        "current_subject": subject if subject in {choice for choice, _ in EduMaterial.SUBJECT_CHOICES} else "",
        "current_material_type": material_type if material_type in {choice for choice, _ in EduMaterial.MaterialType.choices} else "",
        "current_grade": grade,
        "current_tag": tag,
        "subject_choices": EduMaterial.SUBJECT_CHOICES,
        "material_type_choices": EduMaterial.MaterialType.choices,
        "grade_options": grade_options,
        "popular_tags": popular_tags,
    }


def _apply_auto_metadata_with_feedback(request, material):
    metadata = apply_auto_metadata(material, save=True)
    if metadata is None:
        messages.warning(request, "자료는 저장했지만 자동 분류는 잠시 실패했습니다. 직접 메타데이터를 수정할 수 있습니다.")
    return metadata


@login_required
def main_view(request):
    filter_context = _build_filter_context(request)
    my_materials = EduMaterial.objects.filter(teacher=request.user).order_by("-updated_at")
    my_materials = _apply_metadata_filter(
        my_materials,
        query=filter_context["query"],
        subject=filter_context["current_subject"],
        material_type=filter_context["current_material_type"],
        grade=filter_context["current_grade"],
        tag=filter_context["current_tag"],
    )
    shared_materials = list(
        _apply_metadata_filter(
            EduMaterial.objects.select_related("teacher")
        .filter(is_published=True)
        .order_by("-updated_at"),
            query=filter_context["query"],
            subject=filter_context["current_subject"],
            material_type=filter_context["current_material_type"],
            grade=filter_context["current_grade"],
            tag=filter_context["current_tag"],
        )
    )
    for material in shared_materials:
        material.teacher_display_name = _resolve_teacher_display_name(material.teacher)

    return render(
        request,
        "edu_materials/main.html",
        {
            "service": get_service(),
            "my_materials": my_materials,
            "shared_materials": shared_materials,
            "input_mode_choices": EduMaterial.INPUT_MODE_CHOICES,
            **filter_context,
        },
    )


@login_required
@require_POST
def create_material(request):
    title = (request.POST.get("title") or "").strip()
    input_mode = (request.POST.get("input_mode") or EduMaterial.INPUT_PASTE).strip()
    html_content = request.POST.get("html_content", "")
    original_filename = ""

    if input_mode not in {EduMaterial.INPUT_PASTE, EduMaterial.INPUT_FILE}:
        messages.error(request, "입력 방식을 다시 선택해 주세요.")
        return redirect("edu_materials:main")

    if not title:
        messages.error(request, "자료 제목을 입력해 주세요.")
        return redirect("edu_materials:main")

    if input_mode == EduMaterial.INPUT_FILE:
        try:
            metadata = validate_html_upload(request.FILES.get("html_file"))
        except Exception as exc:
            messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
            return redirect("edu_materials:main")
        html_content = metadata["html_content"]
        original_filename = metadata["original_filename"]
    elif not html_content.strip():
        messages.error(request, "붙여넣을 HTML 코드를 입력해 주세요.")
        return redirect("edu_materials:main")

    material = EduMaterial.objects.create(
        teacher=request.user,
        subject="OTHER",
        grade="",
        unit_title="",
        title=title,
        html_content=html_content,
        input_mode=input_mode,
        original_filename=original_filename,
        material_type=EduMaterial.MaterialType.OTHER,
        is_published=True,
    )
    _apply_auto_metadata_with_feedback(request, material)
    messages.success(request, f'"{material.title}" 자료를 저장했고 바로 공개했습니다.')
    return redirect("edu_materials:detail", pk=material.id)


@login_required
@require_POST
def update_material(request, material_id):
    material = get_object_or_404(EduMaterial, id=material_id, teacher=request.user)
    title = (request.POST.get("title") or "").strip()
    html_content = request.POST.get("html_content", "")

    if not title:
        messages.error(request, "자료 제목을 입력해 주세요.")
        return redirect("edu_materials:detail", pk=material.id)

    uploaded_file = request.FILES.get("html_file")
    if uploaded_file:
        try:
            metadata = validate_html_upload(uploaded_file)
        except Exception as exc:
            messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
            return redirect("edu_materials:detail", pk=material.id)
        material.html_content = metadata["html_content"]
        material.original_filename = metadata["original_filename"]
        material.input_mode = EduMaterial.INPUT_FILE
    elif html_content.strip():
        material.html_content = html_content
        material.original_filename = ""
        material.input_mode = EduMaterial.INPUT_PASTE
    else:
        messages.error(request, "HTML 코드를 입력하거나 새 HTML 파일을 올려 주세요.")
        return redirect("edu_materials:detail", pk=material.id)

    material.title = title
    material.save()
    _apply_auto_metadata_with_feedback(request, material)
    messages.success(request, f'"{material.title}" 자료를 수정했습니다.')
    return redirect("edu_materials:detail", pk=material.id)


@login_required
def material_detail(request, pk):
    material = get_object_or_404(EduMaterial, id=pk, teacher=request.user)
    public_url = request.build_absolute_uri(reverse("edu_materials:run", args=[material.id]))
    material_render_url = reverse("edu_materials:render", args=[material.id])
    return render(
        request,
        "edu_materials/detail.html",
        {
            "service": get_service(),
            "material": material,
            "material_render_url": material_render_url,
            "public_url": public_url,
            "public_qr_data_url": build_material_qr_data_url(public_url) if material.is_published else "",
            "metadata_tags_text": ", ".join(material.tags or []),
            "subject_choices": EduMaterial.SUBJECT_CHOICES,
            "material_type_choices": EduMaterial.MaterialType.choices,
            **_build_preview_context(),
        },
    )


@login_required
@require_POST
def update_material_metadata(request, material_id):
    material = get_object_or_404(EduMaterial, id=material_id, teacher=request.user)
    apply_manual_metadata(
        material,
        subject=request.POST.get("subject"),
        grade=request.POST.get("grade"),
        unit_title=request.POST.get("unit_title"),
        material_type=request.POST.get("material_type"),
        tags=parse_tags_input(request.POST.get("tags")),
        summary=request.POST.get("summary"),
        save=True,
    )
    messages.success(request, "메타데이터를 저장했습니다.")
    return redirect("edu_materials:detail", pk=material.id)


@login_required
@require_POST
def reclassify_material(request, material_id):
    material = get_object_or_404(EduMaterial, id=material_id, teacher=request.user)
    metadata = _apply_auto_metadata_with_feedback(request, material)
    if metadata is not None:
        messages.success(request, "현재 자료 내용으로 자동 분류를 다시 계산했습니다.")
    return redirect("edu_materials:detail", pk=material.id)


@login_required
@require_POST
def delete_material(request, material_id):
    material = get_object_or_404(EduMaterial, id=material_id, teacher=request.user)
    title = material.title
    material.delete()
    messages.success(request, f'"{title}" 자료를 삭제했습니다.')
    return redirect("edu_materials:main")


@login_required
@require_POST
def toggle_material_publish(request, material_id):
    material = get_object_or_404(EduMaterial, id=material_id, teacher=request.user)
    action = request.POST.get("action", "toggle")
    if action == "publish":
        material.is_published = True
    elif action == "unpublish":
        material.is_published = False
    else:
        material.is_published = not material.is_published
    material.save(update_fields=["is_published", "updated_at"])
    messages.success(request, "자료 공개 상태를 변경했습니다.")
    return redirect("edu_materials:detail", pk=material.id)


def run_material(request, pk):
    material = get_object_or_404(EduMaterial, id=pk)
    if not material.is_published:
        raise Http404()
    EduMaterial.objects.filter(id=material.id).update(view_count=F("view_count") + 1)
    material.refresh_from_db(fields=["view_count"])
    return render(
        request,
        "edu_materials/run.html",
        {
            "material": material,
            "hide_navbar": True,
            "material_render_url": reverse("edu_materials:render", args=[material.id]),
            **_build_preview_context(),
        },
    )


def render_material(request, pk):
    material = get_object_or_404(EduMaterial, id=pk)
    is_teacher_preview = request.user.is_authenticated and material.teacher_id == request.user.id
    if not material.is_published and not is_teacher_preview:
        raise Http404()

    response = HttpResponse(material.html_content, content_type="text/html; charset=utf-8")
    # Keep raw HTML sandboxed even if the render URL is opened directly.
    response["Content-Security-Policy"] = (
        "sandbox allow-downloads allow-forms allow-modals allow-pointer-lock "
        "allow-popups allow-popups-to-escape-sandbox allow-presentation allow-scripts; "
        "frame-ancestors 'self';"
    )
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response
