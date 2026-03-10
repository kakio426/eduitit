from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
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

HTML_PREVIEW_SAMPLE = """<!doctype html>
<html lang=\"ko\">
<head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>태양계 탐험 안내</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f4f7fb;
            --ink: #14213d;
            --sub: #5b6475;
            --line: rgba(20, 33, 61, 0.12);
            --brand: #2563eb;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            font-family: \"Pretendard\", \"Noto Sans KR\", sans-serif;
            color: var(--ink);
            background:
                radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 26rem),
                linear-gradient(180deg, #fbfdff 0%, var(--bg) 100%);
        }
        .topbar {
            position: sticky;
            top: 0;
            z-index: 20;
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: center;
            padding: 1rem 1.25rem;
            backdrop-filter: blur(10px);
            background: rgba(255, 255, 255, 0.82);
            border-bottom: 1px solid var(--line);
        }
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.45rem 0.8rem;
            border-radius: 999px;
            background: rgba(37, 99, 235, 0.1);
            color: var(--brand);
            font-weight: 700;
            font-size: 0.85rem;
        }
        .shell {
            max-width: 1080px;
            margin: 0 auto;
            padding: 1.5rem 1.25rem 3rem;
        }
        .hero {
            display: grid;
            gap: 1rem;
            padding: 1.5rem;
            border-radius: 1.75rem;
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid var(--line);
            box-shadow: 0 24px 70px rgba(15, 23, 42, 0.08);
        }
        h1 {
            margin: 0;
            font-size: clamp(2rem, 5vw, 3.3rem);
            line-height: 1.06;
        }
        p {
            margin: 0;
            line-height: 1.7;
            color: var(--sub);
        }
        .cta-row {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-top: 0.5rem;
        }
        .cta {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 1rem;
            padding: 0.95rem 1.2rem;
            font-weight: 800;
            text-decoration: none;
            border: 0;
            cursor: pointer;
        }
        .cta.primary {
            background: var(--ink);
            color: white;
        }
        .cta.secondary {
            background: white;
            color: var(--ink);
            border: 1px solid var(--line);
        }
        .grid {
            margin-top: 1rem;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
        }
        .card {
            border-radius: 1.4rem;
            padding: 1.15rem;
            background: white;
            border: 1px solid var(--line);
            min-height: 180px;
        }
        .card strong {
            display: block;
            font-size: 1.05rem;
            margin-bottom: 0.6rem;
        }
        .timeline {
            margin-top: 1rem;
            padding: 1.2rem;
            background: #0f172a;
            border-radius: 1.5rem;
            color: white;
        }
        .timeline ol {
            margin: 0;
            padding-left: 1.2rem;
        }
        .timeline li + li {
            margin-top: 0.7rem;
        }
        .footer-cta {
            margin-top: 1.2rem;
            padding: 1.2rem;
            border-radius: 1.4rem;
            background: linear-gradient(135deg, rgba(37, 99, 235, 0.14), rgba(14, 165, 233, 0.16));
            border: 1px solid rgba(37, 99, 235, 0.18);
        }
    </style>
</head>
<body>
    <div class=\"topbar\">
        <div class=\"badge\">6학년 과학 · 1차시</div>
        <button class=\"cta secondary\" type=\"button\">활동지 받기</button>
    </div>
    <main class=\"shell\">
        <section class=\"hero\">
            <div class=\"badge\">태양계 탐험 미션</div>
            <h1>행성의 특징을 비교하고<br>우리 팀 탐사 계획을 세워 봅시다</h1>
            <p>이 화면은 수업용 HTML 미리보기 예시입니다. sticky 상단, 긴 카드 목록, 아래 CTA까지 함께 들어 있어 비율과 스크롤을 점검하기 좋습니다.</p>
            <div class=\"cta-row\">
                <button class=\"cta primary\" type=\"button\">탐사 미션 시작</button>
                <button class=\"cta secondary\" type=\"button\">핵심 용어 보기</button>
            </div>
        </section>
        <section class=\"grid\">
            <article class=\"card\">
                <strong>수성</strong>
                <p>태양과 가장 가까운 행성입니다. 낮과 밤의 온도 차이가 매우 큽니다.</p>
            </article>
            <article class=\"card\">
                <strong>금성</strong>
                <p>두꺼운 대기 때문에 온실 효과가 강하게 나타납니다.</p>
            </article>
            <article class=\"card\">
                <strong>지구</strong>
                <p>액체 상태의 물과 생명체가 존재하는 행성입니다.</p>
            </article>
            <article class=\"card\">
                <strong>화성</strong>
                <p>붉은색 토양과 거대한 화산이 있는 행성으로 알려져 있습니다.</p>
            </article>
        </section>
        <section class=\"timeline\">
            <h2 style=\"margin-top:0;\">오늘의 수업 흐름</h2>
            <ol>
                <li>행성 카드 읽기</li>
                <li>탐사 우선순위 정하기</li>
                <li>팀별 이유 발표하기</li>
            </ol>
        </section>
        <section class=\"footer-cta\">
            <strong style=\"display:block; margin-bottom:0.5rem;\">정리 질문</strong>
            <p>우리 팀이 가장 먼저 탐사하고 싶은 행성은 어디인가요? 그 이유를 한 문장으로 적어 보세요.</p>
            <div class=\"cta-row\" style=\"margin-top:1rem;\">
                <button class=\"cta primary\" type=\"button\">답 적기</button>
                <button class=\"cta secondary\" type=\"button\">친구 의견 듣기</button>
            </div>
        </section>
    </main>
</body>
</html>
"""


@login_required
def main_view(request):
    materials = TextbookMaterial.objects.filter(teacher=request.user).order_by("-updated_at")
    return render(
        request,
        "textbooks/main.html",
        {
            "service": get_service(),
            "materials": materials,
            "source_choices": TextbookMaterial.SOURCE_CHOICES,
            "subject_choices": TextbookMaterial.SUBJECT_CHOICES,
            "active_classroom": get_active_classroom_for_request(request),
            "html_preview_sample": HTML_PREVIEW_SAMPLE,
        },
    )


@login_required
@require_POST
def create_material(request):
    subject = (request.POST.get("subject") or "").strip()
    grade = (request.POST.get("grade") or "").strip()
    unit_title = (request.POST.get("unit_title") or "").strip()
    title = (request.POST.get("title") or "").strip() or f"{unit_title or '새'} 수업 자료"
    source_type = (request.POST.get("source_type") or TextbookMaterial.SOURCE_HTML).strip()
    content = request.POST.get("content", "")
    uploaded_pdf = request.FILES.get("pdf_file")

    if not subject or not unit_title:
        messages.error(request, "과목과 단원명은 필수입니다.")
        return redirect("textbooks:main")
    if source_type == TextbookMaterial.SOURCE_HTML and not content.strip():
        messages.error(request, "HTML 자료에는 제미나이 코드나 HTML 내용을 붙여넣어 주세요.")
        return redirect("textbooks:main")

    material = TextbookMaterial(
        teacher=request.user,
        subject=subject,
        grade=grade,
        unit_title=unit_title,
        title=title,
        source_type=source_type,
        content=content,
    )
    if source_type == TextbookMaterial.SOURCE_PDF:
        try:
            metadata = validate_pdf_upload(uploaded_pdf)
        except Exception as exc:
            messages.error(request, " ".join(getattr(exc, "messages", [str(exc)])))
            return redirect("textbooks:main")
        material.page_count = metadata["page_count"]
        material.pdf_sha256 = metadata["sha256"]
        material.original_filename = metadata["original_filename"]
        material.pdf_file = uploaded_pdf
    else:
        material.page_count = 0

    try:
        material.full_clean()
    except ValidationError as exc:
        errors = []
        if hasattr(exc, "message_dict"):
            for field_errors in exc.message_dict.values():
                errors.extend(field_errors)
        elif hasattr(exc, "messages"):
            errors.extend(exc.messages)
        if not errors:
            errors.append("자료를 저장하기 전에 입력값을 다시 확인해 주세요.")
        messages.error(request, " ".join(errors))
        return redirect("textbooks:main")

    material.save()

    messages.success(request, f'"{material.title}" 자료를 만들었습니다.')
    return redirect("textbooks:detail", pk=material.id)


@login_required
def material_detail(request, pk):
    material = get_object_or_404(TextbookMaterial, id=pk, teacher=request.user)
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
            "preview_window_url": reverse("textbooks:html_preview_window", args=[material.id]) if material.is_html_document else None,
        },
    )


@login_required
def html_preview_window(request, pk):
    material = get_object_or_404(TextbookMaterial, id=pk, teacher=request.user)
    if not material.is_html_document:
        raise Http404()
    return render(
        request,
        "textbooks/html_preview_window.html",
        {
            "service": get_service(),
            "material": material,
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
