from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import EduMaterial
from .services import build_material_qr_data_url, get_service, validate_html_upload


@login_required
def main_view(request):
    materials = EduMaterial.objects.filter(teacher=request.user).order_by("-updated_at")
    return render(
        request,
        "edu_materials/main.html",
        {
            "service": get_service(),
            "materials": materials,
            "subject_choices": EduMaterial.SUBJECT_CHOICES,
            "input_mode_choices": EduMaterial.INPUT_MODE_CHOICES,
        },
    )


@login_required
@require_POST
def create_material(request):
    subject = (request.POST.get("subject") or "").strip()
    grade = (request.POST.get("grade") or "").strip()
    unit_title = (request.POST.get("unit_title") or "").strip()
    title = (request.POST.get("title") or "").strip() or f"{unit_title or '새'} 교육 자료"
    input_mode = (request.POST.get("input_mode") or EduMaterial.INPUT_PASTE).strip()
    html_content = request.POST.get("html_content", "")
    original_filename = ""

    if input_mode not in {EduMaterial.INPUT_PASTE, EduMaterial.INPUT_FILE}:
        messages.error(request, "입력 방식을 다시 선택해 주세요.")
        return redirect("edu_materials:main")

    if not subject or not unit_title:
        messages.error(request, "과목과 단원명은 필수입니다.")
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
        subject=subject,
        grade=grade,
        unit_title=unit_title,
        title=title,
        html_content=html_content,
        input_mode=input_mode,
        original_filename=original_filename,
    )
    messages.success(request, f'"{material.title}" 자료를 저장했습니다.')
    return redirect("edu_materials:detail", pk=material.id)


@login_required
def material_detail(request, pk):
    material = get_object_or_404(EduMaterial, id=pk, teacher=request.user)
    public_url = request.build_absolute_uri(reverse("edu_materials:run", args=[material.id]))
    return render(
        request,
        "edu_materials/detail.html",
        {
            "service": get_service(),
            "material": material,
            "public_url": public_url,
            "public_qr_data_url": build_material_qr_data_url(public_url) if material.is_published else "",
        },
    )


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
        },
    )
