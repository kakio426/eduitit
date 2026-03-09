from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.active_classroom import get_active_classroom_for_request

from .models import TextbookLiveParticipant, TextbookLiveSession, TextbookMaterial
from .services import (
    build_join_qr_data_url,
    get_or_create_teacher_session,
    get_pdf_access,
    get_service,
    get_session_access,
    issue_student_access_cookie,
    session_snapshot_payload,
    touch_participant,
    validate_pdf_upload,
)


@login_required
def main_view(request):
    materials = TextbookMaterial.objects.filter(
        teacher=request.user,
        source_type=TextbookMaterial.SOURCE_PDF,
    ).order_by("-updated_at")
    return render(
        request,
        "textbooks/main.html",
        {
            "service": get_service(),
            "materials": materials,
            "subject_choices": TextbookMaterial.SUBJECT_CHOICES,
            "active_classroom": get_active_classroom_for_request(request),
        },
    )


@login_required
@require_POST
def create_material(request):
    subject = (request.POST.get("subject") or "").strip()
    grade = (request.POST.get("grade") or "").strip()
    unit_title = (request.POST.get("unit_title") or "").strip()
    title = (request.POST.get("title") or "").strip() or f"{unit_title or '새'} 교과서 PDF"
    content = request.POST.get("content", "")
    uploaded_pdf = request.FILES.get("pdf_file")

    if not subject or not unit_title:
        messages.error(request, "과목과 단원명은 필수입니다.")
        return redirect("textbooks:main")

    try:
        metadata = validate_pdf_upload(uploaded_pdf)
    except Exception as exc:
        messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
        return redirect("textbooks:main")

    material = TextbookMaterial(
        teacher=request.user,
        subject=subject,
        grade=grade,
        unit_title=unit_title,
        title=title,
        source_type=TextbookMaterial.SOURCE_PDF,
        content=content,
        page_count=metadata["page_count"],
        pdf_sha256=metadata["sha256"],
        original_filename=metadata["original_filename"],
        pdf_file=uploaded_pdf,
    )
    material.full_clean()
    material.save()

    messages.success(request, f'"{material.title}" 자료를 만들었습니다.')
    return redirect("textbooks:detail", pk=material.id)


@login_required
def material_detail(request, pk):
    material = get_object_or_404(
        TextbookMaterial,
        id=pk,
        teacher=request.user,
        source_type=TextbookMaterial.SOURCE_PDF,
    )
    active_session = material.live_sessions.filter(
        status__in=[TextbookLiveSession.STATUS_DRAFT, TextbookLiveSession.STATUS_LIVE]
    ).order_by("-created_at").first()
    join_url = request.build_absolute_uri(reverse("textbooks:join_session", args=[active_session.id])) if active_session else None
    display_url = request.build_absolute_uri(reverse("textbooks:display_session", args=[active_session.id])) if active_session else None
    return render(
        request,
        "textbooks/detail.html",
        {
            "service": get_service(),
            "material": material,
            "active_session": active_session,
            "join_url": join_url,
            "join_qr_data_url": build_join_qr_data_url(join_url),
            "display_url": display_url,
        },
    )


@login_required
@require_POST
def toggle_material_publish(request, material_id):
    material = get_object_or_404(
        TextbookMaterial,
        id=material_id,
        teacher=request.user,
        source_type=TextbookMaterial.SOURCE_PDF,
    )
    action = request.POST.get("action", "toggle")
    if action == "publish":
        material.is_published = True
    elif action == "unpublish":
        material.is_published = False
    else:
        material.is_published = not material.is_published
    material.save(update_fields=["is_published", "updated_at"])
    messages.success(request, "자료 공개 상태를 변경했습니다.")
    return redirect("textbooks:detail", pk=material.id)


@require_GET
def material_pdf(request, material_id):
    material = get_object_or_404(
        TextbookMaterial,
        id=material_id,
        source_type=TextbookMaterial.SOURCE_PDF,
    )
    if not material.pdf_file:
        return HttpResponseBadRequest("PDF 자료가 아닙니다.")
    if not get_pdf_access(request, material):
        return HttpResponseForbidden("이 PDF에 접근할 권한이 없습니다.")
    response = FileResponse(material.pdf_file.open("rb"), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{material.original_filename or material.title}.pdf"'
    return response


@login_required
@require_POST
def start_live_session(request, material_id):
    material = get_object_or_404(
        TextbookMaterial,
        id=material_id,
        teacher=request.user,
        source_type=TextbookMaterial.SOURCE_PDF,
    )
    session, created = get_or_create_teacher_session(material, request)
    if created and not material.is_published:
        material.is_published = True
        material.save(update_fields=["is_published", "updated_at"])
    messages.success(request, "라이브 수업 세션을 열었습니다.")
    return redirect("textbooks:teacher_session", session_id=session.id)


@login_required
def teacher_session_view(request, session_id):
    session = get_object_or_404(TextbookLiveSession.objects.select_related("material"), id=session_id, teacher=request.user)
    if not session.material.is_pdf:
        raise Http404()
    touch_participant(
        session,
        role=TextbookLiveParticipant.ROLE_TEACHER,
        device_id=f"teacher-{request.user.id}",
        display_name=request.user.get_username(),
        user=request.user,
        connected=False,
    )
    join_url = request.build_absolute_uri(reverse("textbooks:join_session", args=[session.id]))
    display_url = request.build_absolute_uri(reverse("textbooks:display_session", args=[session.id]))
    return render(
        request,
        "textbooks/live_teacher.html",
        {
            "session": session,
            "material": session.material,
            "pdf_url": reverse("textbooks:material_pdf", args=[session.material_id]) + f"?session={session.id}",
            "join_url": join_url,
            "join_qr_data_url": build_join_qr_data_url(join_url),
            "display_url": display_url,
            "ws_url": f"/ws/textbooks/live/{session.id}/",
        },
    )


@login_required
def display_session_view(request, session_id):
    session = get_object_or_404(TextbookLiveSession.objects.select_related("material"), id=session_id, teacher=request.user)
    if not session.material.is_pdf:
        raise Http404()
    return render(
        request,
        "textbooks/live_display.html",
        {
            "session": session,
            "material": session.material,
            "pdf_url": reverse("textbooks:material_pdf", args=[session.material_id]) + f"?session={session.id}",
            "ws_url": f"/ws/textbooks/live/{session.id}/",
        },
    )


def join_session_view(request, session_id):
    session = get_object_or_404(TextbookLiveSession.objects.select_related("material"), id=session_id)
    if not session.material.is_pdf:
        raise Http404()
    access = get_session_access(request, session)
    if session.status == TextbookLiveSession.STATUS_ENDED:
        return render(request, "textbooks/live_join.html", {"session": session, "ended": True})

    if access and access.get("role") == TextbookLiveParticipant.ROLE_STUDENT:
        touch_participant(
            session,
            role=TextbookLiveParticipant.ROLE_STUDENT,
            device_id=access["device_id"],
            display_name=access.get("display_name") or "학생",
            connected=False,
        )
        return render(
            request,
            "textbooks/live_join.html",
            {
                "session": session,
                "material": session.material,
                "access": access,
                "pdf_url": reverse("textbooks:material_pdf", args=[session.material_id]) + f"?session={session.id}",
                "ws_url": f"/ws/textbooks/live/{session.id}/",
                "verified": True,
            },
        )

    return render(request, "textbooks/live_join.html", {"session": session, "material": session.material, "verified": False})


@require_POST
def verify_join_code(request, session_id):
    session = get_object_or_404(TextbookLiveSession.objects.select_related("material"), id=session_id)
    if not session.material.is_pdf:
        raise Http404()
    submitted_code = (request.POST.get("join_code") or "").strip()
    display_name = (request.POST.get("display_name") or "학생").strip()[:80] or "학생"

    if session.status != TextbookLiveSession.STATUS_LIVE:
        return render(
            request,
            "textbooks/live_join.html",
            {"session": session, "material": session.material, "verified": False, "error": "수업이 아직 시작되지 않았거나 이미 종료되었습니다."},
            status=403,
        )
    if submitted_code != session.join_code:
        return render(
            request,
            "textbooks/live_join.html",
            {"session": session, "material": session.material, "verified": False, "error": "입장 코드가 올바르지 않습니다."},
            status=403,
        )

    response = redirect("textbooks:join_session", session_id=session.id)
    device_id = issue_student_access_cookie(response, session=session, display_name=display_name)
    touch_participant(
        session,
        role=TextbookLiveParticipant.ROLE_STUDENT,
        device_id=device_id,
        display_name=display_name,
        connected=False,
    )
    return response


@require_GET
def bootstrap_session(request, session_id):
    session = get_object_or_404(TextbookLiveSession.objects.select_related("material", "teacher"), id=session_id)
    if not session.material.is_pdf:
        raise Http404()
    access = get_session_access(request, session)
    role = request.GET.get("role") or (access or {}).get("role")
    if not access and role != TextbookLiveParticipant.ROLE_DISPLAY:
        return JsonResponse({"error": "access denied"}, status=403)
    if role == TextbookLiveParticipant.ROLE_DISPLAY and not (request.user.is_authenticated and request.user.id == session.teacher_id):
        return JsonResponse({"error": "display access denied"}, status=403)

    include_private = bool(request.user.is_authenticated and request.user.id == session.teacher_id and role != TextbookLiveParticipant.ROLE_DISPLAY)
    payload = session_snapshot_payload(session, include_private=include_private)
    payload["pdf_url"] = reverse("textbooks:material_pdf", args=[session.material_id]) + f"?session={session.id}"
    payload["viewer_role"] = role or TextbookLiveParticipant.ROLE_STUDENT
    return JsonResponse(payload)


@login_required
@require_POST
def end_live_session(request, session_id):
    session = get_object_or_404(TextbookLiveSession.objects.select_related("material"), id=session_id, teacher=request.user)
    if not session.material.is_pdf:
        raise Http404()
    if session.status != TextbookLiveSession.STATUS_ENDED:
        session.status = TextbookLiveSession.STATUS_ENDED
        session.ended_at = timezone.now()
        session.last_heartbeat = timezone.now()
        session.save(update_fields=["status", "ended_at", "last_heartbeat", "updated_at"])
        channel_layer = get_channel_layer()
        if channel_layer is not None:
            async_to_sync(channel_layer.group_send)(
                f"textbooks-live-{session.id}",
                {
                    "type": "live.broadcast",
                    "message": {
                        "type": "session.end",
                        "seq": session.last_seq + 1,
                        "actor": "teacher",
                        "payload": {"ended": True},
                        "sent_at": timezone.now().isoformat(),
                    },
                },
            )
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    messages.success(request, "라이브 수업을 종료했습니다.")
    return redirect("textbooks:detail", pk=session.material_id)
