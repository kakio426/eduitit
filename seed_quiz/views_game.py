import base64
from io import BytesIO

import qrcode
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from happy_seed.models import HSClassroom, HSStudent
from seed_quiz.models import SQGamePlayer, SQGameQuestion, SQGameRoom
from seed_quiz.services.game_ai import build_multiple_choices
from seed_quiz.services.game_core import (
    advance_phase,
    all_connected_players_done,
    assigned_questions_for_player,
    calculate_rankings,
    clear_game_session,
    create_game_room,
    create_progress_count,
    create_slots_left,
    evaluate_pending_question,
    get_next_question_for_player,
    join_game,
    maybe_auto_advance_room,
    phase_deadline,
    refresh_connection_states,
    set_game_session,
    submit_answer,
    touch_player,
)
from seed_quiz.services.validator import normalize_and_check
from seed_quiz.topics import DEFAULT_TOPIC


def _build_qr_data_url(raw_text: str) -> str:
    if not raw_text:
        return ""
    qr_image = qrcode.make(raw_text)
    with BytesIO() as buffer:
        qr_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _teacher_room_or_404(request, classroom_id, room_id):
    return get_object_or_404(
        SQGameRoom.objects.select_related("classroom", "created_by"),
        id=room_id,
        classroom_id=classroom_id,
        classroom__teacher=request.user,
    )


def _session_player(request):
    room_id = request.session.get("sqg_room_id")
    player_id = request.session.get("sqg_player_id")
    if not room_id or not player_id:
        return None
    player = (
        SQGamePlayer.objects.select_related("game__classroom", "student")
        .filter(id=player_id, game_id=room_id)
        .first()
    )
    if not player:
        clear_game_session(request)
    return player


def _lookup_student(*, room: SQGameRoom, number_raw: str, name: str):
    if not number_raw.isdigit() or not name:
        return None
    number = int(number_raw)
    student = HSStudent.objects.filter(
        classroom=room.classroom,
        number=number,
        name=name,
        is_active=True,
    ).first()
    if student:
        return student
    if number == 0 and name == "선생님":
        student, _ = HSStudent.objects.get_or_create(
            classroom=room.classroom,
            number=0,
            defaults={"name": "선생님", "is_active": True},
        )
        if not student.is_active or student.name != "선생님":
            student.name = "선생님"
            student.is_active = True
            student.save(update_fields=["name", "is_active", "updated_at"])
        return student
    return None


def _phase_seconds_left(room: SQGameRoom) -> int | None:
    deadline = phase_deadline(room)
    if not deadline:
        return None
    return max(0, int((deadline - timezone.now()).total_seconds()))


def _leaderboard(room: SQGameRoom, *, limit: int | None = None):
    players = list(
        room.players.select_related("student")
        .order_by("rank", "joined_at", "student__number", "nickname")
    )
    if limit is not None:
        return players[:limit]
    return players


def _question_rows(room: SQGameRoom):
    rows = []
    questions = list(
        room.questions.select_related("author__student").prefetch_related("answers__player__student").order_by("created_at")
    )
    for question in questions:
        answer_count = question.answers.count()
        correct_count = question.answers.filter(is_correct=True).count()
        rate = round((correct_count / answer_count) * 100) if answer_count else 0
        rows.append(
            {
                "question": question,
                "answer_count": answer_count,
                "correct_count": correct_count,
                "correct_rate": rate,
            }
        )
    return rows


def _player_rows(room: SQGameRoom):
    rows = []
    players = _leaderboard(room)
    for player in players:
        assigned_total = len(assigned_questions_for_player(player))
        rows.append(
            {
                "player": player,
                "created_ready": player.authored_questions.filter(status="ready").count(),
                "created_rejected": player.authored_questions.filter(status="rejected").count(),
                "solved_count": player.answers.count(),
                "solve_target": assigned_total,
            }
        )
    return rows


def _teacher_panel_context(request, room: SQGameRoom, *, error_message: str = ""):
    room = maybe_auto_advance_room(room)
    refresh_connection_states(room)
    room.refresh_from_db()
    players = list(room.players.select_related("student").order_by("rank", "student__number", "nickname"))
    question_counts = room.questions.aggregate(
        total=Count("id"),
        ready=Count("id", filter=Q(status="ready")),
        pending=Count("id", filter=Q(status="pending_ai")),
        rejected=Count("id", filter=Q(status="rejected")),
    )
    create_done_count = sum(create_slots_left(player) == 0 for player in players)
    solve_done_count = sum(get_next_question_for_player(player) is None for player in players) if players else 0
    connected_count = sum(1 for player in players if player.is_connected)
    join_url = request.build_absolute_uri(
        reverse("seed_quiz:student_game_join_code", kwargs={"join_code": room.join_code})
    )
    return {
        "room": room,
        "classroom": room.classroom,
        "players": players,
        "leaderboard": _leaderboard(room),
        "top_leaderboard": _leaderboard(room, limit=5),
        "question_counts": question_counts,
        "create_done_count": create_done_count,
        "solve_done_count": solve_done_count,
        "connected_count": connected_count,
        "seconds_left": _phase_seconds_left(room),
        "join_url": join_url,
        "join_qr_data_url": _build_qr_data_url(join_url),
        "can_start_playing": room.status == "creating" and question_counts["ready"] > 0 and question_counts["pending"] == 0,
        "question_rows": _question_rows(room) if room.status == "finished" else [],
        "player_rows": _player_rows(room) if room.status == "finished" else [],
        "error_message": error_message,
    }


@login_required
def teacher_game_create(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    active_room = classroom.sq_game_rooms.exclude(status="finished").order_by("-created_at").first()
    context = {
        "classroom": classroom,
        "active_room": active_room,
        "topic_choices": SQGameRoom.PRESET_CHOICES,
        "grade_choices": SQGameRoom._meta.get_field("grade").choices,
        "question_mode_choices": SQGameRoom.QUESTION_MODE_CHOICES,
        "defaults": {
            "title": "",
            "topic": DEFAULT_TOPIC,
            "grade": 3,
            "question_mode": "mixed",
            "questions_per_player": 1,
            "solve_target_count": 5,
            "create_minutes": 5,
            "solve_minutes": 5,
            "reward_enabled": True,
        },
        "error_message": "",
    }
    if request.method != "POST":
        return render(request, "seed_quiz/game_teacher_create.html", context)

    try:
        title = (request.POST.get("title") or "").strip()
        topic = (request.POST.get("topic") or DEFAULT_TOPIC).strip()
        grade = int(request.POST.get("grade") or 3)
        question_mode = (request.POST.get("question_mode") or "mixed").strip()
        questions_per_player = int(request.POST.get("questions_per_player") or 1)
        solve_target_count = int(request.POST.get("solve_target_count") or 5)
        create_minutes = int(request.POST.get("create_minutes") or 5)
        solve_minutes = int(request.POST.get("solve_minutes") or 5)
        reward_enabled = request.POST.get("reward_enabled") == "on"
        room = create_game_room(
            classroom=classroom,
            created_by=request.user,
            title=title,
            topic=topic,
            grade=grade,
            question_mode=question_mode,
            questions_per_player=questions_per_player,
            solve_target_count=solve_target_count,
            create_time_seconds=create_minutes * 60,
            solve_time_seconds=solve_minutes * 60,
            reward_enabled=reward_enabled,
        )
        return redirect("seed_quiz:teacher_game_room", classroom_id=classroom.id, room_id=room.id)
    except Exception:
        context["defaults"] = {
            "title": request.POST.get("title") or "",
            "topic": request.POST.get("topic") or DEFAULT_TOPIC,
            "grade": int(request.POST.get("grade") or 3),
            "question_mode": request.POST.get("question_mode") or "mixed",
            "questions_per_player": request.POST.get("questions_per_player") or 1,
            "solve_target_count": request.POST.get("solve_target_count") or 5,
            "create_minutes": request.POST.get("create_minutes") or 5,
            "solve_minutes": request.POST.get("solve_minutes") or 5,
            "reward_enabled": request.POST.get("reward_enabled") == "on",
        }
        context["error_message"] = "입력값을 다시 확인해 주세요."
        return render(request, "seed_quiz/game_teacher_create.html", context)


@login_required
def teacher_game_room(request, classroom_id, room_id):
    room = _teacher_room_or_404(request, classroom_id, room_id)
    return render(
        request,
        "seed_quiz/game_teacher_room.html",
        {
            "room": room,
            "classroom": room.classroom,
        },
    )


@login_required
def htmx_teacher_game_panel(request, classroom_id, room_id):
    room = _teacher_room_or_404(request, classroom_id, room_id)
    return render(
        request,
        "seed_quiz/partials/game_teacher_panel.html",
        _teacher_panel_context(request, room),
    )


@login_required
@require_POST
def htmx_teacher_game_advance(request, classroom_id, room_id):
    room = _teacher_room_or_404(request, classroom_id, room_id)
    requested = (request.POST.get("to_status") or "").strip()
    error_message = ""
    try:
        room = advance_phase(room, to_status=requested or None)
    except ValueError:
        error_message = "준비된 문제가 있어야 풀기를 시작할 수 있습니다."
    return render(
        request,
        "seed_quiz/partials/game_teacher_panel.html",
        _teacher_panel_context(request, room, error_message=error_message),
    )


def student_game_join(request, join_code: str = ""):
    code = (join_code or request.GET.get("code") or "").strip().upper()
    room = SQGameRoom.objects.select_related("classroom").filter(join_code=code).first() if code else None
    error = request.session.pop("sqg_join_error", "")
    if room and room.status == "finished":
        error = "이 게임은 이미 끝났습니다."
        room = None
    return render(
        request,
        "seed_quiz/game_student_join.html",
        {
            "room": room,
            "join_code": code,
            "error_message": error,
        },
    )


@require_POST
def student_game_start(request):
    code = (request.POST.get("join_code") or "").strip().upper()
    room = SQGameRoom.objects.select_related("classroom").filter(join_code=code).first()
    if not room or room.status == "finished":
        request.session["sqg_join_error"] = "입장 코드를 다시 확인해 주세요."
        return redirect("seed_quiz:student_game_join")

    number_raw = (request.POST.get("number") or "").strip()
    name = (request.POST.get("name") or "").strip()
    student = _lookup_student(room=room, number_raw=number_raw, name=name)
    if not student:
        request.session["sqg_join_error"] = "번호와 이름을 다시 확인해 주세요."
        return redirect("seed_quiz:student_game_join_code", join_code=room.join_code)

    player = join_game(room=room, student=student, nickname=name)
    set_game_session(request, room, player)
    return redirect("seed_quiz:student_game_shell")


def student_game_shell(request):
    player = _session_player(request)
    if not player:
        return redirect("seed_quiz:student_game_join")
    return render(
        request,
        "seed_quiz/game_student_shell.html",
        {
            "player": player,
            "room": player.game,
        },
    )


def _student_state_context(player: SQGamePlayer):
    room = maybe_auto_advance_room(player.game)
    player = SQGamePlayer.objects.select_related("game__classroom", "student").get(id=player.id)
    touch_player(player)
    room.refresh_from_db()
    context = {
        "player": player,
        "room": room,
        "classroom": room.classroom,
        "seconds_left": _phase_seconds_left(room),
        "leaderboard": _leaderboard(room, limit=None if room.status == "finished" else 5),
        "assigned_total": len(assigned_questions_for_player(player)) if room.status in {"playing", "finished"} else 0,
        "solved_count": player.answers.count(),
        "create_slots_left": create_slots_left(player),
        "create_count": create_progress_count(player),
        "ready_count": room.questions.filter(status="ready").count(),
    }
    if room.status == "creating":
        context["pending_question"] = (
            player.authored_questions.filter(status="pending_ai").order_by("-submitted_at").first()
        )
    if room.status == "playing":
        context["next_question"] = get_next_question_for_player(player)
        context["all_done"] = all_connected_players_done(room)
    if room.status == "finished":
        context["reward"] = player.rewards.filter(game=room).first()
    return context


@require_GET
def htmx_student_game_state(request):
    player = _session_player(request)
    if not player:
        return HttpResponse(status=403)
    context = _student_state_context(player)
    room = context["room"]
    if room.status == "waiting":
        template = "seed_quiz/partials/game_student_waiting.html"
    elif room.status == "creating":
        if context.get("pending_question"):
            template = "seed_quiz/partials/game_student_pending.html"
        elif context["create_slots_left"] > 0:
            template = "seed_quiz/partials/game_student_create.html"
        else:
            template = "seed_quiz/partials/game_student_waiting.html"
    elif room.status == "playing":
        if context.get("next_question"):
            template = "seed_quiz/partials/game_student_solve.html"
        else:
            template = "seed_quiz/partials/game_student_waiting.html"
    else:
        template = "seed_quiz/partials/game_student_result.html"
    return render(request, template, context)


@require_POST
def htmx_student_game_generate_choices(request):
    player = _session_player(request)
    if not player:
        return HttpResponse(status=403)
    room = player.game
    if room.status != "creating":
        return HttpResponse(status=409)
    question_text = normalize_and_check(request.POST.get("question_text") or "")
    answer_text = normalize_and_check(request.POST.get("answer_text") or "")
    if not question_text or not answer_text:
        return render(
            request,
            "seed_quiz/partials/game_choice_builder.html",
            {"error_message": "문제와 정답을 먼저 적어 주세요."},
        )
    choices, correct_index = build_multiple_choices(
        question=question_text,
        correct_answer=answer_text,
        topic=room.topic,
        grade=room.grade,
    )
    return render(
        request,
        "seed_quiz/partials/game_choice_builder.html",
        {
            "choices": choices,
            "correct_index": correct_index,
            "error_message": "",
        },
    )


@require_POST
def htmx_student_game_submit_question(request):
    player = _session_player(request)
    if not player:
        return HttpResponse(status=403)
    room = player.game
    if room.status != "creating":
        return HttpResponse(status=409)
    if create_slots_left(player) <= 0:
        return render(request, "seed_quiz/partials/game_student_waiting.html", _student_state_context(player))

    question_text = normalize_and_check(request.POST.get("question_text") or "")
    question_type = (request.POST.get("question_type") or room.question_mode or "mc4").strip()
    if room.question_mode in {"ox", "mc4"}:
        question_type = room.question_mode
    if question_type not in {"ox", "mc4"}:
        question_type = "mc4"
    if not question_text:
        context = _student_state_context(player)
        context["error_message"] = "문제를 적어 주세요."
        return render(request, "seed_quiz/partials/game_student_create.html", context)

    choices = []
    answer_text = ""
    correct_index = 0

    if question_type == "ox":
        correct_ox = (request.POST.get("correct_ox") or "O").strip().upper()
        if correct_ox not in {"O", "X"}:
            correct_ox = "O"
        choices = ["O", "X"]
        correct_index = 0 if correct_ox == "O" else 1
        answer_text = choices[correct_index]
    else:
        answer_text = normalize_and_check(request.POST.get("answer_text") or "")
        if not answer_text:
            context = _student_state_context(player)
            context["error_message"] = "정답을 적어 주세요."
            return render(request, "seed_quiz/partials/game_student_create.html", context)
        raw_choices = [(request.POST.get(f"choice_{idx}") or "").strip() for idx in range(4)]
        if not all(raw_choices):
            raw_choices, correct_index = build_multiple_choices(
                question=question_text,
                correct_answer=answer_text,
                topic=room.topic,
                grade=room.grade,
            )
        else:
            raw_choices = [normalize_and_check(item) for item in raw_choices]
            correct_index = int(request.POST.get("correct_index") or 0)
        choices = raw_choices
        if correct_index < 0 or correct_index >= len(choices):
            correct_index = 0
        answer_text = choices[correct_index]

    question = SQGameQuestion.objects.create(
        game=room,
        author=player,
        question_type=question_type,
        question_text=question_text,
        answer_text=answer_text,
        choices=choices,
        correct_index=correct_index,
        status="pending_ai",
        submitted_at=timezone.now(),
    )
    context = _student_state_context(player)
    context["pending_question"] = question
    return render(request, "seed_quiz/partials/game_student_pending.html", context)


@require_GET
def htmx_student_game_question_status(request, question_id):
    player = _session_player(request)
    if not player:
        return HttpResponse(status=403)
    question = get_object_or_404(
        SQGameQuestion.objects.select_related("game", "author"),
        id=question_id,
        game=player.game,
        author=player,
    )
    if question.status == "pending_ai":
        question = evaluate_pending_question(question)
    context = _student_state_context(player)
    context["evaluated_question"] = question
    return render(request, "seed_quiz/partials/game_student_question_result.html", context)


@require_POST
def htmx_student_game_answer(request, question_id):
    player = _session_player(request)
    if not player:
        return HttpResponse(status=403)
    room = player.game
    if room.status != "playing":
        return HttpResponse(status=409)
    question = get_object_or_404(
        SQGameQuestion.objects.select_related("author", "game"),
        id=question_id,
        game=room,
        status="ready",
    )
    selected_raw = (request.POST.get("selected_index") or "").strip()
    if not selected_raw.lstrip("-").isdigit():
        return HttpResponse(status=400)
    selected_index = int(selected_raw)
    if selected_index not in {0, 1, 2, 3}:
        return HttpResponse(status=400)
    time_taken_ms = int(request.POST.get("time_taken_ms") or 0)
    try:
        answer = submit_answer(
            player=player,
            question=question,
            selected_index=selected_index,
            time_taken_ms=time_taken_ms,
        )
    except ValueError:
        return HttpResponseForbidden()

    room = maybe_auto_advance_room(room)
    context = _student_state_context(player)
    context.update(
        {
            "answer": answer,
            "question": question,
            "selected_choice": question.choices[answer.selected_index] if 0 <= answer.selected_index < len(question.choices) else "",
            "correct_choice": question.choices[question.correct_index] if 0 <= question.correct_index < len(question.choices) else "",
        }
    )
    return render(request, "seed_quiz/partials/game_student_feedback.html", context)
