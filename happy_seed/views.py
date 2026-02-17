import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    HSClassroomConfigForm,
    HSClassroomForm,
    HSPrizeForm,
    HSStudentForm,
    StudentBulkAddForm,
)
from .models import (
    HSBloomDraw,
    HSClassroom,
    HSClassroomConfig,
    HSGuardianConsent,
    HSStudent,
)
from .services.engine import (
    ConsentRequiredError,
    InsufficientTicketsError,
    add_seeds,
    execute_bloom_draw,
    get_garden_data,
    grant_tickets,
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
        form = HSClassroomConfigForm(request.POST, instance=config)
        classroom_form = HSClassroomForm(request.POST, instance=classroom)
        if form.is_valid() and classroom_form.is_valid():
            form.save()
            classroom_form.save()
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
    return render(
        request,
        "happy_seed/consent_manage.html",
        {
            "classroom": classroom,
            "students": students,
        },
    )


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
        messages.success(request, f"{student.name}에게 블룸 티켓 {amount}장을 부여했습니다.")
    except ConsentRequiredError:
        messages.error(request, f"{student.name}은(는) 보호자 동의가 필요합니다.")

    return redirect("happy_seed:classroom_detail", classroom_id=classroom.id)


@login_required
def bloom_run(request, classroom_id):
    classroom = get_teacher_classroom(request, classroom_id)
    students_with_tickets = classroom.students.filter(
        is_active=True,
        ticket_count__gt=0,
    ).select_related("consent").order_by("number", "name")
    return render(
        request,
        "happy_seed/bloom_run.html",
        {
            "classroom": classroom,
            "students": students_with_tickets,
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
        celebration_url = f"{redirect('happy_seed:celebration', draw_id=draw.id).url}?token={draw.celebration_token}"
        return redirect(celebration_url)
    except ConsentRequiredError:
        messages.error(request, f"{student.name}은(는) 보호자 동의가 필요합니다.")
    except InsufficientTicketsError:
        messages.error(request, f"{student.name}의 티켓이 부족합니다.")

    return redirect("happy_seed:bloom_run", classroom_id=classroom.id)


@login_required
@require_POST
def seed_grant(request, student_id):
    student = get_object_or_404(HSStudent, id=student_id)
    classroom = get_teacher_classroom(request, student.classroom_id)

    amount = int(request.POST.get("amount", 1))
    detail = request.POST.get("detail", "교사 부여")

    add_seeds(student, amount, "teacher_grant", detail)

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
    return redirect("happy_seed:bloom_run", classroom_id=classroom.id)


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
