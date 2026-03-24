from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .classification import apply_auto_metadata, apply_manual_metadata, collect_popular_tags, parse_tags_input
from .models import EduMaterial
from .runtime import build_runtime_data_url, build_runtime_html
from .services import build_material_qr_data_url, get_service, validate_html_upload


PREVIEW_VIEWPORTS = (
    {"id": "desktop", "label": "Desktop", "width": 1280, "height": 720},
    {"id": "mobile", "label": "Mobile", "width": 390, "height": 844},
)
DEFAULT_PREVIEW_VIEWPORT_ID = "desktop"
TAB_SHARED = "shared"
TAB_MY = "my"
TAB_CREATE = "create"
SORT_LATEST = "latest"
SORT_POPULAR = "popular"
SORT_TITLE = "title"
SORT_CHOICES = (
    (SORT_LATEST, "최신순"),
    (SORT_POPULAR, "인기순"),
    (SORT_TITLE, "제목순"),
)
MY_PAGE_SIZE = 8
SHARED_PAGE_SIZE = 10


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


def _get_filter_accessible_queryset(user, active_tab):
    queryset = EduMaterial.objects.all()
    if not user.is_authenticated:
        return queryset.filter(is_published=True)
    if active_tab in {TAB_MY, TAB_CREATE}:
        return queryset.filter(teacher=user)
    return queryset.filter(is_published=True)


def _resolve_active_tab(request):
    if not request.user.is_authenticated:
        return TAB_SHARED
    requested_tab = (request.GET.get("tab") or "").strip().lower()
    if requested_tab in {TAB_SHARED, TAB_MY, TAB_CREATE}:
        return requested_tab
    return TAB_SHARED


def _resolve_current_sort(request):
    requested_sort = (request.GET.get("sort") or "").strip().lower()
    if requested_sort in {choice for choice, _ in SORT_CHOICES}:
        return requested_sort
    return SORT_LATEST


def _build_query_string(request, *, exclude=()):
    params = request.GET.copy()
    for key in exclude:
        params.pop(key, None)
    return params.urlencode()


def _main_url(*, tab=None):
    url = reverse("edu_materials:main")
    if tab:
        return f"{url}?tab={tab}"
    return url


def _apply_sort(queryset, *, current_sort):
    if current_sort == SORT_POPULAR:
        return queryset.order_by("-view_count", "-updated_at", "-created_at")
    if current_sort == SORT_TITLE:
        return queryset.order_by("title", "-updated_at", "-created_at")
    return queryset.order_by("-updated_at", "-created_at")


def _pick_featured_material(queryset):
    featured = queryset.exclude(summary="").exclude(metadata_status=EduMaterial.MetadataStatus.FAILED).order_by(
        "-view_count",
        "-updated_at",
        "-created_at",
    ).first()
    if featured:
        return featured
    return queryset.order_by("-view_count", "-updated_at", "-created_at").first()


def _build_clone_title(user, source_title):
    base_title = f"{source_title} (내 자료)"
    title = base_title
    suffix = 2
    while EduMaterial.objects.filter(teacher=user, title=title).exists():
        title = f"{base_title} {suffix}"
        suffix += 1
    return title


def _decorate_teacher_display_name(materials):
    for material in materials:
        material.teacher_display_name = _resolve_teacher_display_name(material.teacher)
    return materials


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


def _build_filter_context(request, *, active_tab):
    query = (request.GET.get("q") or "").strip()
    subject = (request.GET.get("subject") or "").strip().upper()
    material_type = (request.GET.get("material_type") or "").strip().lower()
    grade = (request.GET.get("grade") or "").strip()
    tag = (request.GET.get("tag") or "").strip()
    current_sort = _resolve_current_sort(request)

    accessible = _get_filter_accessible_queryset(request.user, active_tab)
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
        "current_sort": current_sort,
        "sort_choices": SORT_CHOICES,
        "subject_choices": EduMaterial.SUBJECT_CHOICES,
        "material_type_choices": EduMaterial.MaterialType.choices,
        "grade_options": grade_options,
        "popular_tags": popular_tags,
    }


def _apply_auto_metadata_with_feedback(request, material):
    metadata = apply_auto_metadata(material, save=True)
    if metadata is None:
        messages.warning(request, "자료는 저장했지만 자동 분류는 잠시 실패했습니다. 직접 분류를 수정할 수 있습니다.")
    return metadata


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


def _build_share_message(*, material, join_url):
    return "\n".join(
        [
            f"[{material.title}]",
            f"학생 입력 주소: {join_url}",
            f"공유 코드: {material.access_code}",
            "QR을 스캔하거나 숫자 코드를 입력해 자료를 여세요.",
        ]
    )


def main_view(request):
    active_tab = _resolve_active_tab(request)
    filter_context = _build_filter_context(request, active_tab=active_tab)
    page_number = request.GET.get("page")

    my_queryset = EduMaterial.objects.none()
    if request.user.is_authenticated:
        my_queryset = _apply_sort(
            _apply_metadata_filter(
                EduMaterial.objects.filter(teacher=request.user),
                query=filter_context["query"],
                subject=filter_context["current_subject"],
                material_type=filter_context["current_material_type"],
                grade=filter_context["current_grade"],
                tag=filter_context["current_tag"],
            ),
            current_sort=filter_context["current_sort"],
        )

    shared_queryset = _apply_sort(
        _apply_metadata_filter(
            EduMaterial.objects.select_related("teacher").filter(is_published=True),
            query=filter_context["query"],
            subject=filter_context["current_subject"],
            material_type=filter_context["current_material_type"],
            grade=filter_context["current_grade"],
            tag=filter_context["current_tag"],
        ),
        current_sort=filter_context["current_sort"],
    )

    featured_public_material = None
    browse_queryset = shared_queryset
    if active_tab == TAB_SHARED:
        featured_public_material = _pick_featured_material(shared_queryset)
        if featured_public_material:
            featured_public_material.teacher_display_name = _resolve_teacher_display_name(featured_public_material.teacher)
            browse_queryset = shared_queryset.exclude(id=featured_public_material.id)

    my_page_obj = Paginator(my_queryset, MY_PAGE_SIZE).get_page(page_number) if request.user.is_authenticated else None
    if my_page_obj is not None:
        my_page_obj.object_list = list(my_page_obj.object_list)

    shared_page_obj = Paginator(browse_queryset, SHARED_PAGE_SIZE).get_page(page_number)
    shared_page_obj.object_list = _decorate_teacher_display_name(list(shared_page_obj.object_list))

    return render(
        request,
        "edu_materials/main.html",
        {
            "service": get_service(),
            "my_page_obj": my_page_obj,
            "shared_page_obj": shared_page_obj,
            "my_material_count": my_queryset.count() if request.user.is_authenticated else 0,
            "shared_material_count": shared_queryset.count(),
            "input_mode_choices": EduMaterial.INPUT_MODE_CHOICES,
            "active_tab": active_tab,
            "tab_query_string": _build_query_string(request, exclude=("tab", "page")),
            "page_query_string": _build_query_string(request, exclude=("page",)),
            "featured_public_material": featured_public_material,
            "show_filter_panel": active_tab != TAB_CREATE,
            "show_create_panel": request.user.is_authenticated and active_tab == TAB_CREATE,
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
        return redirect(_main_url(tab=TAB_CREATE))

    if not title:
        messages.error(request, "자료 제목을 입력해 주세요.")
        return redirect(_main_url(tab=TAB_CREATE))

    if input_mode == EduMaterial.INPUT_FILE:
        try:
            metadata = validate_html_upload(request.FILES.get("html_file"))
        except Exception as exc:
            messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
            return redirect(_main_url(tab=TAB_CREATE))
        html_content = metadata["html_content"]
        original_filename = metadata["original_filename"]
    elif not html_content.strip():
        messages.error(request, "붙여넣을 자료 내용을 입력해 주세요.")
        return redirect(_main_url(tab=TAB_CREATE))

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
    messages.success(request, f'"{material.title}" 자료를 저장했고 학생 공유도 바로 켰습니다. 시작판에서 미리보기와 공유판만 확인해 주세요.')
    return redirect("edu_materials:detail", pk=material.id)


@login_required
@require_POST
def clone_material(request, material_id):
    source = get_object_or_404(EduMaterial.objects.select_related("teacher"), id=material_id, is_published=True)
    if source.teacher_id == request.user.id:
        messages.info(request, "이미 내 자료에 있는 자료입니다.")
        return redirect("edu_materials:detail", pk=source.id)

    clone = EduMaterial.objects.create(
        teacher=request.user,
        title=_build_clone_title(request.user, source.title),
        html_content=source.html_content,
        input_mode=source.input_mode,
        original_filename=source.original_filename,
        is_published=True,
    )
    apply_manual_metadata(
        clone,
        subject=source.subject,
        grade=source.grade,
        unit_title=source.unit_title,
        material_type=source.material_type,
        tags=list(source.tags or []),
        summary=source.summary,
        save=True,
    )
    messages.success(request, f'"{source.title}" 자료를 내 자료로 가져왔고 학생 공유도 바로 켰습니다. 시작판에서 바로 확인해 주세요.')
    return redirect("edu_materials:detail", pk=clone.id)


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
        messages.error(request, "자료 내용을 붙여넣거나 새 자료 파일을 올려 주세요.")
        return redirect("edu_materials:detail", pk=material.id)

    material.title = title
    material.save()
    _apply_auto_metadata_with_feedback(request, material)
    messages.success(request, f'"{material.title}" 자료를 수정했습니다.')
    return redirect("edu_materials:detail", pk=material.id)


def material_detail(request, pk):
    material = get_object_or_404(EduMaterial.objects.select_related("teacher"), id=pk)
    is_owner = request.user.is_authenticated and material.teacher_id == request.user.id
    if not is_owner and not material.is_published:
        raise Http404()

    public_url = request.build_absolute_uri(reverse("edu_materials:run", args=[material.id]))
    student_join_url = request.build_absolute_uri(reverse("edu_materials:join_short"))
    student_join_display = f"{request.get_host()}{reverse('edu_materials:join_short')}"
    material_render_url = reverse("edu_materials:render", args=[material.id])
    response = render(
        request,
        "edu_materials/detail.html",
        {
            "service": get_service(),
            "material": material,
            "is_owner": is_owner,
            "can_manage": is_owner,
            "can_clone": request.user.is_authenticated and not is_owner,
            "teacher_display_name": _resolve_teacher_display_name(material.teacher),
            "material_frame_src": build_runtime_data_url(material.html_content),
            "material_render_url": material_render_url,
            "student_join_url": student_join_url,
            "student_join_display": student_join_display,
            "share_board_url": reverse("edu_materials:share_board", args=[material.id]),
            "public_qr_data_url": build_material_qr_data_url(public_url),
            "share_message": _build_share_message(material=material, join_url=student_join_url),
            "metadata_tags_text": ", ".join(material.tags or []),
            "subject_choices": EduMaterial.SUBJECT_CHOICES,
            "material_type_choices": EduMaterial.MaterialType.choices,
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
            material = EduMaterial.objects.filter(access_code=normalized_code, is_published=True).first()
            if material:
                return redirect("edu_materials:run", pk=material.id)

            hidden_material = EduMaterial.objects.filter(access_code=normalized_code).first()
            if hidden_material:
                error_message = "이 자료는 아직 학생 공유가 열리지 않았습니다. 선생님께 공개 여부를 확인해 주세요."
            else:
                error_message = "입력한 공유 코드를 찾지 못했습니다. 선생님이 보여준 6자리 숫자를 다시 확인해 주세요."

    return render(
        request,
        "edu_materials/join.html",
        {
            "service": get_service(),
            "submitted_code": normalized_code,
            "error_message": error_message,
        },
    )


def share_board(request, pk):
    material = get_object_or_404(EduMaterial.objects.select_related("teacher"), id=pk)
    is_owner = request.user.is_authenticated and material.teacher_id == request.user.id
    if not material.is_published and not is_owner:
        raise Http404()

    student_join_display = f"{request.get_host()}{reverse('edu_materials:join_short')}"
    public_url = request.build_absolute_uri(reverse("edu_materials:run", args=[material.id]))
    return render(
        request,
        "edu_materials/share_board.html",
        {
            "material": material,
            "hide_navbar": True,
            "is_owner": is_owner,
            "teacher_display_name": _resolve_teacher_display_name(material.teacher),
            "student_join_display": student_join_display,
            "public_qr_data_url": build_material_qr_data_url(public_url),
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
    messages.success(request, "분류를 저장했습니다.")
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
    if not material.is_published:
        material.is_published = True
        material.save(update_fields=["is_published", "updated_at"])
        messages.success(request, "교육자료실 자료는 항상 공개됩니다. 기존 비공개 자료도 공개로 바꿨습니다.")
    else:
        messages.info(request, "교육자료실 자료는 항상 공개됩니다.")
    return redirect("edu_materials:detail", pk=material.id)


def run_material(request, pk):
    material = get_object_or_404(EduMaterial, id=pk)
    if not material.is_published:
        raise Http404()
    EduMaterial.objects.filter(id=material.id).update(view_count=F("view_count") + 1)
    material.refresh_from_db(fields=["view_count"])
    response = render(
        request,
        "edu_materials/run.html",
        {
            "material": material,
            "hide_navbar": True,
            "material_frame_src": build_runtime_data_url(material.html_content),
            "material_render_url": reverse("edu_materials:render", args=[material.id]),
            **_build_preview_context(),
        },
    )
    return _append_csp_update(response, {"frame-src": ("data:",)})


def render_material(request, pk):
    material = get_object_or_404(EduMaterial, id=pk)
    is_teacher_preview = request.user.is_authenticated and material.teacher_id == request.user.id
    if not material.is_published and not is_teacher_preview:
        raise Http404()

    response = HttpResponse(build_runtime_html(material.html_content), content_type="text/html; charset=utf-8")
    # Keep raw HTML sandboxed even if the render URL is opened directly.
    response["Content-Security-Policy"] = (
        "sandbox allow-downloads allow-forms allow-modals allow-pointer-lock "
        "allow-popups allow-popups-to-escape-sandbox allow-presentation allow-scripts; "
        "frame-ancestors 'self';"
    )
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    return response
