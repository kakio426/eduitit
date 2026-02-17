import uuid
import random
import re
from uuid import UUID
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    HSActivityForm,
    HSClassroomConfigForm,
    HSClassroomForm,
    HSPrizeForm,
    HSStudentForm,
    StudentBulkAddForm,
)
from .models import (
    HSActivity,
    HSActivityScore,
    HSBloomDraw,
    HSClassEventLog,
    HSClassroom,
    HSClassroomConfig,
    HSGuardianConsent,
    HSInterventionLog,
    HSStudentGroup,
    HSStudent,
)
from .services.engine import (
    ConsentRequiredError,
    InsufficientTicketsError,
    NoPrizeAvailableError,
    add_seeds,
    execute_bloom_draw,
    get_garden_data,
    grant_tickets,
    log_class_event,
)


def _request_id(request):
    return request.headers.get("X-Request-Id") or str(uuid.uuid4())


def _api_ok(request, data, status=200):
    return JsonResponse(
        {"ok": True, "data": data, "error": None, "request_id": _request_id(request)},
        status=status,
    )


def _api_err(request, code, message, status=400, details=None):
    return JsonResponse(
        {
            "ok": False,
            "data": None,
            "error": {"code": code, "message": message, "details": details or {}},
            "request_id": _request_id(request),
        },
        status=status,
    )


def get_teacher_classroom(request, classroom_id):
    return get_object_or_404(
        HSClassroom,
        id=classroom_id,
        teacher=request.user,
        is_active=True,
    )


def landing(request):
    return render(request, "happy_seed/landing.html")


@login_required
def teacher_manual(request):
    return render(request, "happy_seed/teacher_manual.html")


@login_required
def dashboard(request):
    classrooms = HSClassroom.objects.filter(
        teacher=request.user,
        is_active=True,
    ).order_by("-created_at")
    return render(request, "happy_seed/dashboard.html", {"classrooms": classrooms})


@login_required
def classroom_create(request):
    if request.method == "POST":
        form = HSClassroomForm(request.POST)
        if form.is_valid():
            classroom = form.save(commit=False)
            classroom.teacher = request.user
            classroom.save()
            HSClassroomConfig.objects.create(classroom=classroom)
            messages.success(request, f'"{classroom.name}" 교실이 생성되었습니다.')
            return redirect("happy_seed:classroom_detail", classroom_id=classroom.id)
    else:
        form = HSClassroomForm()
    return render(request, "happy_seed/classroom_form.html", {"form": form, "is_create": True})


@login_required
def classroom_detail(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    config, _ = HSClassroomConfig.objects.get_or_create(classroom=classroom)
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    return render(
        request,
        "happy_seed/classroom_detail.html",
        {
            "classroom": classroom,
            "config": config,
            "students": students,
        },
    )


@login_required
def classroom_settings(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    config, _ = HSClassroomConfig.objects.get_or_create(classroom=classroom)

    if request.method == "POST":
        prev_balance_enabled = config.balance_mode_enabled
        form = HSClassroomConfigForm(request.POST, instance=config)
        classroom_form = HSClassroomForm(request.POST, instance=classroom)
        if form.is_valid() and classroom_form.is_valid():
            form.save()
            classroom_form.save()
            if prev_balance_enabled != config.balance_mode_enabled:
                log_class_event(
                    classroom,
                    "WARM_BALANCE_MODE_TOGGLED",
                    meta={"enabled": config.balance_mode_enabled},
                )
            messages.success(request, "설정이 저장되었습니다.")
            return redirect("happy_seed:classroom_settings", classroom_id=classroom.id)
    else:
        form = HSClassroomConfigForm(instance=config)
        classroom_form = HSClassroomForm(instance=classroom)

    return render(
        request,
        "happy_seed/classroom_settings.html",
        {
            "classroom": classroom,
            "config": config,
            "form": form,
            "classroom_form": classroom_form,
        },
    )


@login_required
@require_POST
def student_add(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    form = HSStudentForm(request.POST)
    if form.is_valid():
        student = form.save(commit=False)
        student.classroom = classroom
        student.save()
        HSGuardianConsent.objects.create(student=student)
        students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
        return render(
            request,
            "happy_seed/partials/student_grid.html",
            {
                "classroom": classroom,
                "students": students,
            },
        )
    return render(
        request,
        "happy_seed/partials/student_grid.html",
        {
            "classroom": classroom,
            "students": classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name"),
            "error": "학생 추가에 실패했습니다.",
        },
    )


@login_required
def student_bulk_add(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    if request.method == "POST":
        form = StudentBulkAddForm(request.POST)
        if form.is_valid():
            parsed = form.parse_students()
            created_count = 0
            for item in parsed:
                student, created = HSStudent.objects.get_or_create(
                    classroom=classroom,
                    number=item["number"],
                    defaults={"name": item["name"]},
                )
                if created:
                    HSGuardianConsent.objects.create(student=student)
                    created_count += 1
            messages.success(request, f"{created_count}명의 학생을 추가했습니다.")
            return redirect("happy_seed:classroom_detail", classroom_id=classroom.id)
    else:
        form = StudentBulkAddForm()
    return render(
        request,
        "happy_seed/student_bulk_add.html",
        {
            "classroom": classroom,
            "form": form,
        },
    )


@login_required
@require_POST
def student_edit(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)
    form = HSStudentForm(request.POST, instance=student)
    if form.is_valid():
        form.save()
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    return render(
        request,
        "happy_seed/partials/student_grid.html",
        {
            "classroom": classroom,
            "students": students,
        },
    )


@login_required
def consent_manage(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    sign_talk_url = ""
    for student in students:
        consent = getattr(student, "consent", None)
        if consent and consent.external_url:
            sign_talk_url = consent.external_url
            break
    unmatched_signatures = []
    if sign_talk_url:
        from signatures.models import Signature, TrainingSession

        match = re.search(r"/sign/([0-9a-fA-F-]+)/", sign_talk_url)
        if match:
            session = TrainingSession.objects.filter(uuid=UUID(match.group(1))).first()
            if session:
                signed_names = set(
                    Signature.objects.filter(training_session=session).values_list("participant_name", flat=True)
                )
                classroom_names = set(students.values_list("name", flat=True))
                unmatched_signatures = sorted(name for name in signed_names if name not in classroom_names)
    return render(
        request,
        "happy_seed/consent_manage.html",
        {
            "classroom": classroom,
            "students": students,
            "sign_talk_url": sign_talk_url,
            "unmatched_signatures": unmatched_signatures,
            "pending_students": [s for s in students if s.consent.status != "approved"],
        },
    )


@login_required
@require_POST
def consent_request_via_sign_talk(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)

    from signatures.models import TrainingSession

    now = timezone.now()
    title = f"[행복의 씨앗] {classroom.name} 보호자 동의"

    session = TrainingSession.objects.filter(
        created_by=request.user,
        title=title,
        is_active=True,
    ).order_by("-created_at").first()

    if session is None:
        session = TrainingSession.objects.create(
            title=title,
            instructor=request.user.get_full_name() or request.user.username,
            datetime=now,
            location=classroom.school_name or classroom.name,
            description=(
                f"{classroom.name} 보호자 동의를 위한 서명톡 페이지입니다. "
                "보호자 성함과 서명을 제출해 주세요."
            ),
            created_by=request.user,
            is_active=True,
        )

    sign_url = request.build_absolute_uri(
        reverse("signatures:sign", kwargs={"uuid": session.uuid})
    )

    HSGuardianConsent.objects.filter(
        student__classroom=classroom,
        student__is_active=True,
    ).update(
        external_url=sign_url,
        requested_at=now,
    )
    for student in classroom.students.filter(is_active=True):
        log_class_event(
            classroom,
            "CONSENT_REQUEST_SENT",
            student=student,
            meta={"external_url": sign_url},
        )

    messages.success(request, "서명톡 동의 링크를 생성하고 학생 동의 항목에 연동했습니다.")
    return redirect("happy_seed:consent_manage", classroom_id=classroom.id)


@login_required
@require_POST
def consent_resend(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)
    consent, _ = HSGuardianConsent.objects.get_or_create(student=student)
    if not consent.external_url:
        messages.error(request, "먼저 서명톡 링크를 생성해 주세요.")
        return redirect("happy_seed:consent_manage", classroom_id=classroom.id)
    consent.requested_at = timezone.now()
    consent.save(update_fields=["requested_at", "updated_at"])
    log_class_event(classroom, "CONSENT_REQUEST_SENT", student=student, meta={"resend": True})
    messages.success(request, f"{student.name} 학생 동의 요청을 재발송 처리했습니다.")
    return redirect("happy_seed:consent_manage", classroom_id=classroom.id)


@login_required
@require_POST
def consent_sync_from_sign_talk(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    from signatures.models import Signature, TrainingSession

    sample_consent = classroom.students.filter(is_active=True).select_related("consent").first()
    if not sample_consent or not getattr(sample_consent, "consent", None) or not sample_consent.consent.external_url:
        messages.error(request, "연동된 서명톡 링크가 없어 동기화할 수 없습니다.")
        return redirect("happy_seed:consent_manage", classroom_id=classroom.id)

    match = re.search(r"/sign/([0-9a-fA-F-]+)/", sample_consent.consent.external_url)
    if not match:
        messages.error(request, "서명톡 링크 형식을 확인할 수 없습니다.")
        return redirect("happy_seed:consent_manage", classroom_id=classroom.id)
    session_uuid = UUID(match.group(1))
    session = TrainingSession.objects.filter(uuid=session_uuid).first()
    if not session:
        messages.error(request, "서명 세션을 찾을 수 없습니다.")
        return redirect("happy_seed:consent_manage", classroom_id=classroom.id)

    signatures = Signature.objects.filter(training_session=session).values_list("participant_name", flat=True)
    signed_names = set(signatures)
    classroom_names = set(classroom.students.filter(is_active=True).values_list("name", flat=True))
    unmatched_signature_count = len([name for name in signed_names if name not in classroom_names])
    updated = 0
    for student in classroom.students.filter(is_active=True).select_related("consent"):
        if student.name in signed_names and student.consent.status != "approved":
            student.consent.status = "approved"
            student.consent.completed_at = timezone.now()
            student.consent.save(update_fields=["status", "completed_at", "updated_at"])
            log_class_event(classroom, "CONSENT_SIGNED", student=student)
            updated += 1

    messages.success(request, f"서명 결과를 동기화했습니다. 동의 완료 {updated}명, 명단 미일치 {unmatched_signature_count}건")
    return redirect("happy_seed:consent_manage", classroom_id=classroom.id)


@login_required
@require_POST
def consent_manual_approve(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    student_id = request.POST.get("student_id", "")
    signer_name = request.POST.get("signer_name", "").strip()
    student = HSStudent.objects.filter(id=student_id, classroom=classroom, is_active=True).select_related("consent").first()
    if not student:
        messages.error(request, "학생을 찾을 수 없습니다.")
        return redirect("happy_seed:consent_manage", classroom_id=classroom.id)
    student.consent.status = "approved"
    student.consent.completed_at = timezone.now()
    student.consent.save(update_fields=["status", "completed_at", "updated_at"])
    log_class_event(
        classroom,
        "CONSENT_SIGNED",
        student=student,
        meta={"by": "teacher_manual_review", "signer_name": signer_name},
    )
    messages.success(request, f"수동 확인 승인 완료: {student.name} (서명자: {signer_name or '-'})")
    return redirect("happy_seed:consent_manage", classroom_id=classroom.id)


@login_required
@require_POST
def consent_update(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)
    consent, _ = HSGuardianConsent.objects.get_or_create(student=student)

    new_status = request.POST.get("status", "")
    if new_status in dict(HSGuardianConsent.STATUS_CHOICES):
        consent.status = new_status
        if new_status == "approved":
            consent.completed_at = timezone.now()
            student.is_active = True
            log_class_event(classroom, "CONSENT_SIGNED", student=student, meta={"by": "teacher_manual"})
        if new_status == "withdrawn":
            student.is_active = False
            student.save()
        consent.save()

    return render(
        request,
        "happy_seed/partials/consent_row.html",
        {
            "student": student,
            "classroom": classroom,
        },
    )


@login_required
def prize_manage(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)

    if request.method == "POST":
        form = HSPrizeForm(request.POST)
        if form.is_valid():
            prize = form.save(commit=False)
            prize.classroom = classroom
            prize.save()
            messages.success(request, f'보상 "{prize.name}"을 추가했습니다.')
            return redirect("happy_seed:prize_manage", classroom_id=classroom.id)
    else:
        form = HSPrizeForm()

    prizes = classroom.prizes.all()
    return render(
        request,
        "happy_seed/prize_manage.html",
        {
            "classroom": classroom,
            "prizes": prizes,
            "form": form,
        },
    )


@login_required
@require_POST
def bloom_grant(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    student_id = request.POST.get("student_id")
    source = request.POST.get("source", "participation")
    amount = int(request.POST.get("amount", 1))

    student = get_object_or_404(HSStudent, id=student_id, classroom=classroom)

    try:
        grant_tickets(student, source, amount, detail=f"{source} 인정")
        event_type = "TOKEN_GRANTED_SCORE_BONUS" if source == "achievement" else "TOKEN_GRANTED_DILIGENT"
        log_class_event(classroom, event_type, student=student, meta={"amount": amount, "source": source})
        messages.success(request, f"{student.name}에게 블룸 티켓 {amount}장을 부여했습니다.")
    except ConsentRequiredError:
        messages.error(request, f"{student.name}은(는) 보호자 동의가 필요합니다.")

    return redirect("happy_seed:classroom_detail", classroom_id=classroom.id)


@login_required
def bloom_run(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    has_rewards = classroom.has_available_rewards
    config, _ = HSClassroomConfig.objects.get_or_create(classroom=classroom)
    students_with_tickets = classroom.students.filter(
        is_active=True,
        ticket_count__gt=0,
    ).select_related("consent").order_by("number", "name")
    groups = HSStudentGroup.objects.filter(classroom=classroom).prefetch_related("members__consent").order_by("name")
    group_infos = []
    for g in groups:
        eligible = [
            m for m in g.members.all()
            if m.is_active and getattr(m, "consent", None) and m.consent.status == "approved"
        ]
        group_infos.append({"group": g, "eligible_count": len(eligible), "member_count": g.members.count()})
    draw = None
    token = ""
    draw_id = request.GET.get("draw", "")
    if draw_id:
        draw = HSBloomDraw.objects.filter(id=draw_id, student__classroom=classroom).select_related("student", "prize").first()
        if draw:
            token = str(draw.celebration_token)
    return render(
        request,
        "happy_seed/bloom_run.html",
        {
            "classroom": classroom,
            "students": students_with_tickets,
            "has_rewards": has_rewards,
            "group_infos": group_infos,
            "default_group_draw_count": max(1, min(2, config.group_draw_count)),
            "last_draw": draw,
            "last_draw_token": token,
        },
    )


@login_required
@require_POST
def bloom_draw(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)

    request_id_str = request.POST.get("request_id", "")
    try:
        request_id = uuid.UUID(request_id_str) if request_id_str else uuid.uuid4()
    except ValueError:
        request_id = uuid.uuid4()

    try:
        draw = execute_bloom_draw(student, classroom, request.user, request_id)
        return redirect(f"{reverse('happy_seed:bloom_run', kwargs={'classroom_id': classroom.id})}?draw={draw.id}")
    except ConsentRequiredError:
        messages.error(request, f"{student.name}은(는) 보호자 동의가 필요합니다.")
    except InsufficientTicketsError:
        messages.error(request, f"{student.name}의 티켓이 부족합니다.")
    except NoPrizeAvailableError:
        messages.error(request, "사용 가능한 보상이 없습니다. 보상을 먼저 등록하거나 재고를 확인해 주세요.")

    return redirect("happy_seed:bloom_run", classroom_id=classroom.id)


@login_required
@require_POST
def seed_grant(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)

    amount = int(request.POST.get("amount", 1))
    detail = request.POST.get("detail", "교사 부여")

    add_seeds(student, amount, "teacher_grant", detail)
    log_class_event(classroom, "SEED_GRANTED_MANUAL", student=student, meta={"amount": amount, "detail": detail})

    student.refresh_from_db()
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    return render(
        request,
        "happy_seed/partials/student_grid.html",
        {
            "classroom": classroom,
            "students": students,
        },
    )


def celebration(request, draw_id):
    draw = get_object_or_404(HSBloomDraw, id=draw_id)
    token = request.GET.get("token", "")

    if str(draw.celebration_token) != token:
        return HttpResponseForbidden("접근 권한이 없습니다.")

    if draw.celebration_closed:
        return render(
            request,
            "happy_seed/celebration.html",
            {
                "draw": draw,
                "closed": True,
            },
        )

    return render(
        request,
        "happy_seed/celebration.html",
        {
            "draw": draw,
            "closed": False,
        },
    )


@login_required
@require_POST
def close_celebration(request, draw_id):
    draw = get_object_or_404(HSBloomDraw, id=draw_id)
    classroom = get_teacher_classroom(request, draw.student.classroom_id)
    draw.celebration_closed = True
    draw.celebration_token = uuid.uuid4()
    draw.save()
    return redirect(f"{reverse('happy_seed:bloom_run', kwargs={'classroom_id': classroom.id})}?draw={draw.id}")


def garden_public(request, slug):
    classroom = get_object_or_404(HSClassroom, slug=slug, is_active=True)
    flowers = get_garden_data(classroom)
    return render(
        request,
        "happy_seed/garden_public.html",
        {
            "classroom": classroom,
            "flowers": flowers,
        },
    )


@login_required
def activity_manage(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    activities = HSActivity.objects.filter(classroom=classroom).order_by("-id")[:20]

    if request.method == "POST":
        form = HSActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.classroom = classroom
            activity.save()

            for student in students:
                if student.consent.status != "approved":
                    continue
                diligent = request.POST.get(f"diligent_{student.id}") == "on"
                manual_bonus = request.POST.get(f"bonus_manual_{student.id}") == "on"
                score_val = request.POST.get(f"score_{student.id}", "").strip()
                score = int(score_val) if score_val.isdigit() else 0
                HSActivityScore.objects.update_or_create(
                    activity=activity,
                    student=student,
                    defaults={"score": score},
                )
                if diligent:
                    grant_tickets(student, "participation", 1, detail=f"[{activity.title}] 성실 참여")
                    log_class_event(
                        classroom,
                        "TOKEN_GRANTED_DILIGENT",
                        student=student,
                        meta={"activity_id": activity.id, "activity_title": activity.title},
                    )
                if manual_bonus or score >= activity.threshold_score:
                    grant_tickets(
                        student,
                        "achievement",
                        activity.extra_bloom_count,
                        detail=f"[{activity.title}] 우수 성취",
                    )
                    HSActivityScore.objects.filter(activity=activity, student=student).update(bloom_granted=True)
                    log_class_event(
                        classroom,
                        "TOKEN_GRANTED_SCORE_BONUS",
                        student=student,
                        meta={
                            "activity_id": activity.id,
                            "activity_title": activity.title,
                            "score": score,
                            "threshold": activity.threshold_score,
                            "extra": activity.extra_bloom_count,
                            "manual_bonus": manual_bonus,
                        },
                    )

            messages.success(request, "활동 저장 및 지급 적용이 완료되었습니다.")
            return redirect("happy_seed:activity_manage", classroom_id=classroom.id)
    else:
        form = HSActivityForm()

    return render(
        request,
        "happy_seed/activity_manage.html",
        {
            "classroom": classroom,
            "students": students,
            "activities": activities,
            "form": form,
        },
    )


@login_required
def analysis_dashboard(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    lookback_days = int(request.GET.get("days", "30"))
    since = timezone.now() - timezone.timedelta(days=lookback_days)
    students = list(classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name"))
    draws = HSBloomDraw.objects.filter(student__classroom=classroom, drawn_at__gte=since)
    wins = draws.filter(is_win=True).count()
    total = draws.count()
    win_rate = round((wins / total) * 100, 2) if total else 0

    stats = []
    for student in students:
        s_draws = draws.filter(student=student)
        s_wins = s_draws.filter(is_win=True).count()
        loss_streak = 0
        for d in s_draws.order_by("-drawn_at"):
            if d.is_win:
                break
            loss_streak += 1
        stats.append(
            {
                "student": student,
                "wins": s_wins,
                "draws": s_draws.count(),
                "loss_streak": loss_streak,
                "seed_count": student.seed_count,
            }
        )

    alerts = []
    long_no_win = [s for s in stats if s["draws"] >= 3 and s["wins"] == 0]
    if long_no_win:
        alerts.append(f"최근 {lookback_days}일 기준 장기 미당첨 학생 {len(long_no_win)}명")
    if stats:
        sorted_wins = sorted(stats, key=lambda x: x["wins"], reverse=True)
        top2 = sum(item["wins"] for item in sorted_wins[:2])
        if wins > 0 and top2 / wins >= 0.6:
            alerts.append("당첨 편중 가능성이 있습니다. 상위 2명 집중도를 확인해 주세요.")
        seed_stagnant = [s for s in stats if s["seed_count"] == 0 and s["draws"] == 0]
        if seed_stagnant:
            alerts.append(f"씨앗/추첨 기록이 없는 학생 {len(seed_stagnant)}명")

    intervention_logs = HSInterventionLog.objects.filter(classroom=classroom).select_related("student", "created_by")[:20]
    return render(
        request,
        "happy_seed/analysis_dashboard.html",
        {
            "classroom": classroom,
            "lookback_days": lookback_days,
            "total_draws": total,
            "wins": wins,
            "win_rate": win_rate,
            "stats": stats,
            "alerts": alerts,
            "intervention_logs": intervention_logs,
        },
    )


@login_required
def group_manage(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    groups = HSStudentGroup.objects.filter(classroom=classroom).prefetch_related("members").order_by("name")
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "create":
            name = request.POST.get("group_name", "").strip()
            if not name:
                messages.error(request, "모둠 이름을 입력해 주세요.")
            else:
                HSStudentGroup.objects.create(classroom=classroom, name=name)
                messages.success(request, f"모둠 '{name}' 생성 완료")
            return redirect("happy_seed:group_manage", classroom_id=classroom.id)
        if action == "delete":
            group = HSStudentGroup.objects.filter(classroom=classroom, id=request.POST.get("group_id")).first()
            if group:
                group.delete()
                messages.success(request, "모둠을 삭제했습니다.")
            return redirect("happy_seed:group_manage", classroom_id=classroom.id)
        if action == "save_members":
            group = HSStudentGroup.objects.filter(classroom=classroom, id=request.POST.get("group_id")).first()
            if not group:
                messages.error(request, "모둠을 찾을 수 없습니다.")
                return redirect("happy_seed:group_manage", classroom_id=classroom.id)
            member_ids = request.POST.getlist("member_ids")
            members = HSStudent.objects.filter(classroom=classroom, id__in=member_ids, is_active=True)
            group.members.set(members)
            messages.success(request, f"{group.name} 구성 저장 완료")
            return redirect("happy_seed:group_manage", classroom_id=classroom.id)

    return render(
        request,
        "happy_seed/group_manage.html",
        {
            "classroom": classroom,
            "groups": groups,
            "students": students,
        },
    )


@login_required
@require_POST
def set_teacher_override(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)
    reason = request.POST.get("reason", "").strip()
    student.pending_forced_win = True
    student.save(update_fields=["pending_forced_win"])
    HSInterventionLog.objects.create(
        classroom=classroom,
        student=student,
        action="forced_win_next",
        detail=reason,
        created_by=request.user,
    )
    log_class_event(
        classroom,
        "TEACHER_OVERRIDE_SET",
        student=student,
        meta={"reason": reason},
    )
    messages.success(request, f"{student.name} 학생에게 다음 꽃피움 강제당첨을 예약했습니다.")
    next_url = request.POST.get("next") or reverse("happy_seed:bloom_run", kwargs={"classroom_id": classroom.id})
    return redirect(next_url)


@login_required
@require_POST
def group_mission_success(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    group_id = request.POST.get("group_id", "")
    draw_count = request.POST.get("draw_count", "1")
    try:
        draw_count = int(draw_count)
    except ValueError:
        draw_count = 1
    draw_count = 1 if draw_count < 1 else 2 if draw_count > 2 else draw_count

    group = HSStudentGroup.objects.filter(classroom=classroom, id=group_id).prefetch_related("members__consent").first()
    if not group:
        messages.error(request, "모둠을 선택해 주세요.")
        return redirect("happy_seed:bloom_run", classroom_id=classroom.id)

    eligible = [
        m for m in group.members.all()
        if m.is_active and getattr(m, "consent", None) and m.consent.status == "approved"
    ]
    if len(eligible) < draw_count:
        messages.error(request, "모둠 인원이 부족합니다. (동의 완료 학생 기준)")
        return redirect("happy_seed:bloom_run", classroom_id=classroom.id)

    winners = random.sample(eligible, draw_count)
    winner_names = []
    for student in winners:
        grant_tickets(student, "group_draw", 1, detail=f"[{group.name}] 모둠 미션 성공")
        log_class_event(
            classroom,
            "GROUP_MISSION_REWARD",
            student=student,
            group=group,
            meta={"group_name": group.name, "draw_count": draw_count},
        )
        winner_names.append(student.name)

    messages.success(request, f"모둠 미션 성공: {group.name}에서 {', '.join(winner_names)} 학생에게 티켓 +1 지급")
    return redirect("happy_seed:bloom_run", classroom_id=classroom.id)


@login_required
@require_POST
def api_execute_draw(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return _api_err(request, "ERR_INVALID_REQUEST", "요청 본문(JSON)을 확인해 주세요.", status=400)

    student_id = body.get("student_id")
    if not student_id:
        return _api_err(request, "ERR_INVALID_REQUEST", "student_id가 필요합니다.", status=400)
    student = HSStudent.objects.filter(id=student_id, classroom=classroom).first()
    if not student:
        return _api_err(request, "ERR_NOT_FOUND", "학생을 찾을 수 없습니다.", status=404)

    raw_key = request.headers.get("Idempotency-Key") or body.get("idempotency_key") or str(uuid.uuid4())
    try:
        request_id = uuid.UUID(str(raw_key))
    except ValueError:
        request_id = uuid.uuid4()

    try:
        draw = execute_bloom_draw(student, classroom, request.user, request_id=request_id)
    except ConsentRequiredError:
        return _api_err(request, "ERR_CONSENT_REQUIRED", "동의 완료 후 사용할 수 있습니다.", status=400)
    except InsufficientTicketsError:
        return _api_err(request, "ERR_TOKEN_INSUFFICIENT", "꽃피움권이 부족합니다.", status=400)
    except NoPrizeAvailableError:
        return _api_err(request, "ERR_REWARD_EMPTY", "사용 가능한 보상이 없습니다.", status=400)

    student.refresh_from_db()
    return _api_ok(
        request,
        {
            "event_id": str(draw.id),
            "result": "WIN" if draw.is_win else "LOSE",
            "reward": (
                {"reward_id": str(draw.prize.id), "title_text": draw.prize.name}
                if draw.prize
                else None
            ),
            "student_state": {
                "student_id": str(student.id),
                "tokens_available": student.ticket_count,
                "seeds_balance": student.seed_count,
            },
            "display_overlay": {
                "show": True,
                "student_name": student.name,
                "message_footer": "나의 작은 행동 하나하나가 나의 미래, 너의 미래, 우리 모두의 미래를 행복으로 바꿉니다.",
            },
        },
    )


@login_required
@require_POST
def api_group_mission_success(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    try:
        body = json.loads(request.body.decode("utf-8")) if request.body else {}
    except json.JSONDecodeError:
        return _api_err(request, "ERR_INVALID_REQUEST", "요청 본문(JSON)을 확인해 주세요.", status=400)

    group_id = body.get("group_id")
    winners_count = int(body.get("winners_count", 1))
    winners_count = 1 if winners_count < 1 else 2 if winners_count > 2 else winners_count
    group = HSStudentGroup.objects.filter(classroom=classroom, id=group_id).prefetch_related("members__consent").first()
    if not group:
        return _api_err(request, "ERR_NOT_FOUND", "모둠을 찾을 수 없습니다.", status=404)

    eligible = [
        m for m in group.members.all()
        if m.is_active and getattr(m, "consent", None) and m.consent.status == "approved"
    ]
    if len(eligible) < winners_count:
        return _api_err(
            request,
            "ERR_GROUP_TOO_SMALL",
            "모둠 인원이 부족합니다.",
            status=400,
            details={"eligible_count": len(eligible), "requested_count": winners_count},
        )

    winners = random.sample(eligible, winners_count)
    for student in winners:
        grant_tickets(student, "group_draw", 1, detail=f"[{group.name}] 모둠 미션 성공")
        log_class_event(
            classroom,
            "GROUP_MISSION_REWARD",
            student=student,
            group=group,
            meta={"group_name": group.name, "draw_count": winners_count},
        )
    return _api_ok(
        request,
        {
            "group_id": str(group.id),
            "group_name": group.name,
            "winner_student_ids": [str(s.id) for s in winners],
            "winner_names": [s.name for s in winners],
        },
    )


@login_required
@require_POST
def api_consent_sync_sign_talk(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    before = HSGuardianConsent.objects.filter(student__classroom=classroom, status="approved").count()
    response = consent_sync_from_sign_talk(request, classroom_id)
    after = HSGuardianConsent.objects.filter(student__classroom=classroom, status="approved").count()
    if isinstance(response, JsonResponse):
        return response
    return _api_ok(
        request,
        {
            "approved_before": before,
            "approved_after": after,
            "approved_delta": max(0, after - before),
        },
    )


@login_required
def student_grid_partial(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    students = classroom.students.filter(is_active=True).select_related("consent").order_by("number", "name")
    return render(
        request,
        "happy_seed/partials/student_grid.html",
        {
            "classroom": classroom,
            "students": students,
        },
    )


def garden_partial(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, is_active=True)
    flowers = get_garden_data(classroom)
    return render(
        request,
        "happy_seed/partials/garden_flowers.html",
        {
            "classroom": classroom,
            "flowers": flowers,
        },
    )


def student_tooltip_partial(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id, is_active=True)
    config, _ = HSClassroomConfig.objects.get_or_create(classroom=student.classroom)
    return render(
        request,
        "happy_seed/partials/student_tooltip.html",
        {
            "student": student,
            "config": config,
        },
    )
