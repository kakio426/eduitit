import base64
import uuid
from io import BytesIO

import qrcode
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
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
    review_question,
    set_game_session,
    submit_answer,
    submit_question,
    touch_player,
)
from seed_quiz.services.validator import normalize_and_check
from seed_quiz.topics import DEFAULT_TOPIC

TEACHER_GAME_DEFAULTS = {
    "title": "",
    "topic": DEFAULT_TOPIC,
    "grade": "3",
    "question_mode": "mixed",
    "questions_per_player": "1",
    "solve_target_count": "5",
    "create_minutes": "5",
    "solve_minutes": "5",
    "reward_enabled": True,
}


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
        room.questions.filter(status="ready")
        .select_related("author__student")
        .prefetch_related("answers__player__student")
        .order_by("created_at")
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


def _coerce_request_id(raw_request_id) -> str:
    raw_value = str(raw_request_id or "").strip()
    if not raw_value:
        return str(uuid.uuid4())
    try:
        return str(uuid.UUID(raw_value))
    except (TypeError, ValueError, AttributeError):
        return str(uuid.uuid4())


def _coerce_int(raw_value, *, minimum: int | None = None, maximum: int | None = None):
    raw_text = str(raw_value or "").strip()
    if not raw_text or not raw_text.lstrip("-").isdigit():
        return None
    value = int(raw_text)
    if minimum is not None and value < minimum:
        return None
    if maximum is not None and value > maximum:
        return None
    return value


def _normalize_text(raw_value, *, error_message: str) -> tuple[str, str]:
    try:
        return normalize_and_check(raw_value or ""), ""
    except ValueError:
        return "", error_message


def _teacher_form_defaults(post=None) -> dict:
    defaults = dict(TEACHER_GAME_DEFAULTS)
    if post is None:
        return defaults
    defaults.update(
        {
            "title": (post.get("title") or "").strip(),
            "topic": (post.get("topic") or defaults["topic"]).strip() or defaults["topic"],
            "grade": (post.get("grade") or defaults["grade"]).strip() or defaults["grade"],
            "question_mode": (post.get("question_mode") or defaults["question_mode"]).strip() or defaults["question_mode"],
            "questions_per_player": (post.get("questions_per_player") or defaults["questions_per_player"]).strip()
            or defaults["questions_per_player"],
            "solve_target_count": (post.get("solve_target_count") or defaults["solve_target_count"]).strip()
            or defaults["solve_target_count"],
            "create_minutes": (post.get("create_minutes") or defaults["create_minutes"]).strip()
            or defaults["create_minutes"],
            "solve_minutes": (post.get("solve_minutes") or defaults["solve_minutes"]).strip()
            or defaults["solve_minutes"],
            "reward_enabled": post.get("reward_enabled") == "on",
        }
    )
    return defaults


def _teacher_create_context(classroom, *, active_room=None, defaults=None, error_message: str = ""):
    return {
        "classroom": classroom,
        "active_room": active_room if active_room is not None else classroom.sq_game_rooms.exclude(status="finished").order_by("-created_at").first(),
        "topic_choices": SQGameRoom.PRESET_CHOICES,
        "grade_choices": SQGameRoom._meta.get_field("grade").choices,
        "question_mode_choices": SQGameRoom.QUESTION_MODE_CHOICES,
        "defaults": defaults or _teacher_form_defaults(),
        "error_message": error_message,
    }


def _parse_teacher_create_form(post) -> tuple[dict | None, dict, str]:
    defaults = _teacher_form_defaults(post)
    title, title_error = _normalize_text(defaults["title"], error_message="이름을 다시 확인해 주세요.")
    if title_error:
        return None, defaults, title_error

    topic_values = {str(value) for value, _label in SQGameRoom.PRESET_CHOICES}
    topic = defaults["topic"] if defaults["topic"] in topic_values else ""
    if not topic:
        return None, defaults, "주제를 다시 확인해 주세요."

    grade_values = {int(value) for value, _label in SQGameRoom._meta.get_field("grade").choices}
    grade = _coerce_int(defaults["grade"])
    if grade not in grade_values:
        return None, defaults, "학년을 다시 확인해 주세요."

    question_mode_values = {str(value) for value, _label in SQGameRoom.QUESTION_MODE_CHOICES}
    question_mode = defaults["question_mode"] if defaults["question_mode"] in question_mode_values else ""
    if not question_mode:
        return None, defaults, "형식을 다시 확인해 주세요."

    questions_per_player = _coerce_int(defaults["questions_per_player"], minimum=1, maximum=3)
    if questions_per_player is None:
        return None, defaults, "출제 수를 다시 확인해 주세요."

    solve_target_count = _coerce_int(defaults["solve_target_count"], minimum=1, maximum=20)
    if solve_target_count is None:
        return None, defaults, "풀이 수를 다시 확인해 주세요."

    create_minutes = _coerce_int(defaults["create_minutes"], minimum=1, maximum=30)
    if create_minutes is None:
        return None, defaults, "출제 시간을 다시 확인해 주세요."

    solve_minutes = _coerce_int(defaults["solve_minutes"], minimum=1, maximum=30)
    if solve_minutes is None:
        return None, defaults, "풀이 시간을 다시 확인해 주세요."

    cleaned = {
        "title": title,
        "topic": topic,
        "grade": grade,
        "question_mode": question_mode,
        "questions_per_player": questions_per_player,
        "solve_target_count": solve_target_count,
        "create_minutes": create_minutes,
        "solve_minutes": solve_minutes,
        "reward_enabled": defaults["reward_enabled"],
    }
    defaults.update({"grade": str(grade)})
    return cleaned, defaults, ""


def _default_form_state(room: SQGameRoom, *, request_id: str | None = None) -> dict:
    default_type = room.question_mode if room.question_mode in {"ox", "mc4"} else "mc4"
    return {
        "request_id": request_id or str(uuid.uuid4()),
        "question_type": default_type,
        "question_text": "",
        "answer_text": "",
        "correct_ox": "O",
        "choices": [],
        "correct_index": 0,
        "choice_fallback": False,
    }


def _form_state_from_post(request, room: SQGameRoom) -> dict:
    form_state = _default_form_state(room, request_id=_coerce_request_id(request.POST.get("request_id")))
    question_type = (request.POST.get("question_type") or form_state["question_type"]).strip()
    if room.question_mode in {"ox", "mc4"}:
        question_type = room.question_mode
    if question_type not in {"ox", "mc4"}:
        question_type = "mc4"
    correct_index_raw = (request.POST.get("correct_index") or "0").strip()
    correct_index = int(correct_index_raw) if correct_index_raw.lstrip("-").isdigit() else 0
    form_state.update(
        {
            "question_type": question_type,
            "question_text": (request.POST.get("question_text") or "").strip(),
            "answer_text": (request.POST.get("answer_text") or "").strip(),
            "correct_ox": (request.POST.get("correct_ox") or "O").strip().upper() or "O",
            "choices": [(request.POST.get(f"choice_{idx}") or "").strip() for idx in range(4)],
            "correct_index": correct_index,
        }
    )
    return form_state


def _student_state_template(context: dict) -> str:
    room = context["room"]
    if room.status == "waiting":
        return "seed_quiz/partials/game_student_waiting.html"
    if room.status == "creating":
        if context.get("pending_question"):
            return "seed_quiz/partials/game_student_pending.html"
        if context.get("needs_review_question"):
            return "seed_quiz/partials/game_student_waiting.html"
        if context["create_slots_left"] > 0:
            return "seed_quiz/partials/game_student_create.html"
        return "seed_quiz/partials/game_student_waiting.html"
    if room.status == "playing":
        if context.get("next_question"):
            return "seed_quiz/partials/game_student_solve.html"
        return "seed_quiz/partials/game_student_waiting.html"
    return "seed_quiz/partials/game_student_result.html"


def _render_student_state(request, player: SQGamePlayer, *, context: dict | None = None):
    context = context or _student_state_context(player)
    return render(request, _student_state_template(context), context)


def _render_student_create(request, player: SQGamePlayer, *, error_message: str = "", form_state: dict | None = None):
    context = _student_state_context(player)
    context["error_message"] = error_message
    context["form_state"] = form_state or context.get("form_state") or _default_form_state(context["room"])
    return render(request, "seed_quiz/partials/game_student_create.html", context)


def _render_student_solve(request, player: SQGamePlayer, *, error_message: str = ""):
    context = _student_state_context(player)
    if not context.get("next_question"):
        return _render_student_state(request, player, context=context)
    context["error_message"] = error_message
    return render(request, "seed_quiz/partials/game_student_solve.html", context)


def _render_choice_builder(
    request,
    *,
    error_message: str = "",
    choices=None,
    correct_index: int = 0,
    fallback_used: bool = False,
    status: int = 200,
):
    return render(
        request,
        "seed_quiz/partials/game_choice_builder.html",
        {
            "choices": choices or [],
            "correct_index": correct_index,
            "fallback_used": fallback_used,
            "error_message": error_message,
        },
        status=status,
    )


def _play_block_message(question_counts: dict) -> str:
    pending = int(question_counts.get("pending") or 0)
    needs_review = int(question_counts.get("needs_review") or 0)
    ready = int(question_counts.get("ready") or 0)
    if pending > 0:
        return f"AI 확인 {pending}개를 기다리는 중입니다."
    if needs_review > 0:
        return f"검토 대기 {needs_review}개를 먼저 처리하세요."
    if ready < 1:
        return "사용할 문제가 아직 없습니다."
    return ""


def _teacher_panel_context(request, room: SQGameRoom, *, error_message: str = ""):
    room = maybe_auto_advance_room(room)
    refresh_connection_states(room)
    room.refresh_from_db()
    players = list(room.players.select_related("student").order_by("rank", "student__number", "nickname"))
    question_counts = room.questions.aggregate(
        total=Count("id"),
        ready=Count("id", filter=Q(status="ready")),
        pending=Count("id", filter=Q(status="pending_ai")),
        needs_review=Count("id", filter=Q(status="needs_review")),
        rejected=Count("id", filter=Q(status="rejected")),
    )
    create_done_count = sum(create_slots_left(player) == 0 for player in players)
    solve_done_count = sum(get_next_question_for_player(player) is None for player in players) if players else 0
    connected_count = sum(1 for player in players if player.is_connected)
    leaderboard = _leaderboard(room)
    play_block_message = _play_block_message(question_counts) if room.status == "creating" else ""
    join_url = request.build_absolute_uri(
        reverse("seed_quiz:student_game_join_code", kwargs={"join_code": room.join_code})
    )
    return {
        "room": room,
        "classroom": room.classroom,
        "players": players,
        "leaderboard": leaderboard,
        "top_leaderboard": leaderboard[:5],
        "question_counts": question_counts,
        "create_done_count": create_done_count,
        "solve_done_count": solve_done_count,
        "connected_count": connected_count,
        "seconds_left": _phase_seconds_left(room),
        "join_url": join_url,
        "join_qr_data_url": _build_qr_data_url(join_url),
        "review_queue": list(
            room.questions.filter(status="needs_review")
            .select_related("author__student")
            .order_by("submitted_at", "created_at")
        ),
        "play_block_message": play_block_message,
        "can_start_playing": room.status == "creating" and not play_block_message,
        "winner": leaderboard[0] if leaderboard and leaderboard[0].rank else None,
        "question_rows": _question_rows(room) if room.status == "finished" else [],
        "player_rows": _player_rows(room) if room.status == "finished" else [],
        "error_message": error_message,
    }


@login_required
def teacher_game_create(request, classroom_id):
    classroom = get_object_or_404(HSClassroom, id=classroom_id, teacher=request.user)
    active_room = classroom.sq_game_rooms.exclude(status="finished").order_by("-created_at").first()
    context = _teacher_create_context(classroom, active_room=active_room)
    if request.method != "POST":
        return render(request, "seed_quiz/game_teacher_create.html", context)

    cleaned, defaults, error_message = _parse_teacher_create_form(request.POST)
    if error_message or not cleaned:
        context = _teacher_create_context(
            classroom,
            active_room=active_room,
            defaults=defaults,
            error_message=error_message or "입력값을 다시 확인해 주세요.",
        )
        return render(request, "seed_quiz/game_teacher_create.html", context)

    room = create_game_room(
        classroom=classroom,
        created_by=request.user,
        title=cleaned["title"],
        topic=cleaned["topic"],
        grade=cleaned["grade"],
        question_mode=cleaned["question_mode"],
        questions_per_player=cleaned["questions_per_player"],
        solve_target_count=cleaned["solve_target_count"],
        create_time_seconds=cleaned["create_minutes"] * 60,
        solve_time_seconds=cleaned["solve_minutes"] * 60,
        reward_enabled=cleaned["reward_enabled"],
    )
    return redirect("seed_quiz:teacher_game_room", classroom_id=classroom.id, room_id=room.id)


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
    except ValueError as exc:
        error_map = {
            "pending_ai_remaining": "AI 확인이 끝난 뒤에 풀기를 시작할 수 있습니다.",
            "needs_review_remaining": "검토 대기를 먼저 처리해 주세요.",
            "ready_questions_required": "준비된 문제가 있어야 풀기를 시작할 수 있습니다.",
        }
        error_message = error_map.get(str(exc), "진행 상태를 바꾸지 못했습니다.")
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
        "top_leaderboard": _leaderboard(room, limit=5),
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
        context["needs_review_question"] = (
            player.authored_questions.filter(status="needs_review").order_by("-submitted_at", "-created_at").first()
        )
        context["form_state"] = _default_form_state(room)
        if context.get("needs_review_question"):
            context["waiting_state"] = "needs_review"
        elif context["create_slots_left"] > 0:
            context["waiting_state"] = "ready_to_create"
        else:
            context["waiting_state"] = "submitted"
    if room.status == "playing":
        context["next_question"] = get_next_question_for_player(player)
        context["all_done"] = all_connected_players_done(room)
        if not context.get("next_question"):
            context["waiting_state"] = "result_pending"
    if room.status == "waiting":
        context["waiting_state"] = "before_start"
    if room.status == "finished":
        context["reward"] = player.rewards.filter(game=room).first()
    return context


@require_GET
def htmx_student_game_state(request):
    player = _session_player(request)
    if not player:
        return HttpResponse(status=403)
    return _render_student_state(request, player)


@require_POST
def htmx_student_game_generate_choices(request):
    player = _session_player(request)
    if not player:
        return _render_choice_builder(request, error_message="다시 들어와 주세요.")
    room = player.game
    if room.status != "creating":
        return _render_choice_builder(request, error_message="지금은 보기를 만들 수 없습니다.")
    question_text, question_error = _normalize_text(
        request.POST.get("question_text"),
        error_message="문제 글자를 다시 확인해 주세요.",
    )
    if question_error:
        return _render_choice_builder(request, error_message=question_error)
    answer_text, answer_error = _normalize_text(
        request.POST.get("answer_text"),
        error_message="정답 글자를 다시 확인해 주세요.",
    )
    if answer_error:
        return _render_choice_builder(request, error_message=answer_error)
    if not question_text or not answer_text:
        return _render_choice_builder(request, error_message="문제와 정답을 먼저 적어 주세요.")
    choices, correct_index, fallback_used = build_multiple_choices(
        question=question_text,
        correct_answer=answer_text,
        topic=room.topic,
        grade=room.grade,
    )
    return _render_choice_builder(
        request,
        choices=choices,
        correct_index=correct_index,
        fallback_used=fallback_used,
    )


@require_POST
def htmx_student_game_submit_question(request):
    player = _session_player(request)
    if not player:
        return HttpResponse(status=403)
    room = player.game
    if room.status != "creating":
        return _render_student_state(request, player)

    form_state = _form_state_from_post(request, room)
    question_text, question_error = _normalize_text(
        request.POST.get("question_text"),
        error_message="문제 글자를 다시 확인해 주세요.",
    )
    if question_error:
        return _render_student_create(request, player, error_message=question_error, form_state=form_state)
    question_type = (request.POST.get("question_type") or room.question_mode or "mc4").strip()
    if room.question_mode in {"ox", "mc4"}:
        question_type = room.question_mode
    if question_type not in {"ox", "mc4"}:
        question_type = "mc4"
    form_state["question_type"] = question_type
    if not question_text:
        form_state["question_text"] = ""
        return _render_student_create(request, player, error_message="문제를 적어 주세요.", form_state=form_state)

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
        form_state["correct_ox"] = correct_ox
    else:
        answer_text, answer_error = _normalize_text(
            request.POST.get("answer_text"),
            error_message="정답 글자를 다시 확인해 주세요.",
        )
        if answer_error:
            return _render_student_create(request, player, error_message=answer_error, form_state=form_state)
        if not answer_text:
            form_state["answer_text"] = ""
            return _render_student_create(request, player, error_message="정답을 적어 주세요.", form_state=form_state)
        raw_choices = [(request.POST.get(f"choice_{idx}") or "").strip() for idx in range(4)]
        if not all(raw_choices):
            raw_choices, correct_index, used_fallback = build_multiple_choices(
                question=question_text,
                correct_answer=answer_text,
                topic=room.topic,
                grade=room.grade,
            )
            form_state["choice_fallback"] = used_fallback
        else:
            try:
                raw_choices = [normalize_and_check(item) for item in raw_choices]
            except ValueError:
                return _render_student_create(
                    request,
                    player,
                    error_message="보기 글자를 다시 확인해 주세요.",
                    form_state=form_state,
                )
            if any(not item for item in raw_choices):
                form_state["choices"] = raw_choices
                return _render_student_create(
                    request,
                    player,
                    error_message="보기를 다시 확인해 주세요.",
                    form_state=form_state,
                )
            if len(set(raw_choices)) != len(raw_choices):
                form_state["choices"] = raw_choices
                return _render_student_create(
                    request,
                    player,
                    error_message="보기는 서로 다르게 적어 주세요.",
                    form_state=form_state,
                )
            correct_index_raw = (request.POST.get("correct_index") or "").strip()
            if not correct_index_raw.lstrip("-").isdigit():
                form_state["choices"] = raw_choices
                return _render_student_create(
                    request,
                    player,
                    error_message="정답 위치를 다시 선택해 주세요.",
                    form_state=form_state,
                )
            correct_index = int(correct_index_raw)
        choices = raw_choices
        form_state["choices"] = choices
        if correct_index < 0 or correct_index >= len(choices):
            form_state["correct_index"] = 0
            return _render_student_create(
                request,
                player,
                error_message="정답 위치를 다시 확인해 주세요.",
                form_state=form_state,
            )
        form_state["correct_index"] = correct_index
        answer_text = choices[correct_index]

    try:
        question, _ = submit_question(
            player=player,
            request_id=form_state["request_id"],
            question_type=question_type,
            question_text=question_text,
            answer_text=answer_text,
            choices=choices,
            correct_index=correct_index,
        )
    except ValueError as exc:
        if str(exc) in {"invalid_phase", "no_slots_left"}:
            return _render_student_state(request, player)
        return _render_student_create(
            request,
            player,
            error_message="제출을 다시 시도해 주세요.",
            form_state=form_state,
        )
    context = _student_state_context(player)
    if question.status == "pending_ai":
        context["pending_question"] = question
        return render(request, "seed_quiz/partials/game_student_pending.html", context)
    if question.status in {"ready", "needs_review"}:
        context["evaluated_question"] = question
        return render(request, "seed_quiz/partials/game_student_question_result.html", context)
    return _render_student_state(request, player, context=context)


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
        return _render_student_state(request, player)
    question = (
        SQGameQuestion.objects.select_related("author", "game")
        .filter(id=question_id, game=room, status="ready")
        .first()
    )
    if not question:
        return _render_student_solve(request, player, error_message="지금 문제부터 풀어 주세요.")
    selected_raw = (request.POST.get("selected_index") or "").strip()
    if not selected_raw.lstrip("-").isdigit():
        return _render_student_solve(request, player, error_message="답을 다시 골라 주세요.")
    selected_index = int(selected_raw)
    if selected_index < 0 or selected_index >= len(question.choices or []):
        return _render_student_solve(request, player, error_message="답을 다시 골라 주세요.")
    time_taken_raw = (request.POST.get("time_taken_ms") or "0").strip()
    time_taken_ms = int(time_taken_raw) if time_taken_raw.isdigit() else 0
    try:
        answer = submit_answer(
            player=player,
            question=question,
            selected_index=selected_index,
            time_taken_ms=time_taken_ms,
        )
    except ValueError as exc:
        error_map = {
            "invalid_choice": "답을 다시 골라 주세요.",
            "cannot_answer_own_question": "지금 문제부터 풀어 주세요.",
            "invalid_question": "지금 문제부터 풀어 주세요.",
            "not_assigned_question": "지금 문제부터 풀어 주세요.",
        }
        if str(exc) in error_map:
            return _render_student_solve(request, player, error_message=error_map[str(exc)])
        return _render_student_state(request, player)

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


@login_required
@require_POST
def htmx_teacher_game_review(request, classroom_id, room_id, question_id):
    room = _teacher_room_or_404(request, classroom_id, room_id)
    question = get_object_or_404(SQGameQuestion, id=question_id, game=room)
    error_message = ""
    if room.status != "creating":
        error_message = "출제 단계에서만 검토할 수 있습니다."
    else:
        try:
            review_question(question=question, action=request.POST.get("action") or "")
        except ValueError:
            error_message = "검토 처리에 실패했습니다."
    room.refresh_from_db()
    return render(
        request,
        "seed_quiz/partials/game_teacher_panel.html",
        _teacher_panel_context(request, room, error_message=error_message),
    )
