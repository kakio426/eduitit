import json
import random

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import MathGameMove, MathGameSession
from .services import game_2048, nim, twenty_four


def _student_games_mode(request):
    return bool(request.session.get("dutyticker_student_games_mode"))


def _ensure_session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ""


def _request_payload(request) -> dict:
    content_type = request.META.get("CONTENT_TYPE", "")
    if "application/json" in content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


def _wants_json(request) -> bool:
    return "application/json" in request.headers.get("Accept", "") or not getattr(request, "htmx", False)


def _response(request, payload: dict, *, status: int = 200, partial_template: str = ""):
    if not _wants_json(request) and partial_template:
        return render(request, partial_template, payload, status=status)
    return JsonResponse(payload, status=status)


def _session_owner(request):
    return request.user if request.user.is_authenticated else None


def _nim_public_payload(session: MathGameSession, *, feedback: str = "", ai_move=None, thought: str = "") -> dict:
    history = list(session.state_json.get("history") or [])
    _game, state = nim.apply_history(history)
    result = session.result
    return {
        "session_id": str(session.id),
        "state": nim.state_to_payload(state, history, result=result),
        "result": result,
        "feedback": feedback,
        "ai_move": ai_move,
        "thought": thought,
        "legal_moves": nim.legal_take_options(getattr(state, "piles", ())),
    }


def _twenty_four_state(session: MathGameSession) -> dict:
    state = dict(session.state_json or {})
    return {
        "numbers": list(state.get("numbers") or []),
        "hints_used": int(state.get("hints_used") or 0),
        "status": session.result,
    }


def _twenty_four_payload(session: MathGameSession, *, feedback: str = "", value_text: str = "", hint: str = "") -> dict:
    return {
        "session_id": str(session.id),
        "state": _twenty_four_state(session),
        "result": session.result,
        "feedback": feedback,
        "value": value_text,
        "hint": hint,
    }


def _game_2048_payload(session: MathGameSession, *, feedback: str = "") -> dict:
    return {
        "session_id": str(session.id),
        "state": game_2048.public_state(session.state_json),
        "result": session.result,
        "feedback": feedback,
    }


@require_GET
def index(request):
    return render(
        request,
        "math_games/index.html",
        {
            "hide_navbar": _student_games_mode(request),
        },
    )


@require_GET
@ensure_csrf_cookie
def nim_page(request):
    return render(
        request,
        "math_games/nim.html",
        {
            "hide_navbar": _student_games_mode(request),
        },
    )


@require_GET
@ensure_csrf_cookie
def twenty_four_page(request):
    return render(
        request,
        "math_games/twenty_four.html",
        {
            "hide_navbar": _student_games_mode(request),
        },
    )


@require_GET
@ensure_csrf_cookie
def game_2048_page(request):
    return render(
        request,
        "math_games/game_2048.html",
        {
            "hide_navbar": _student_games_mode(request),
        },
    )


@require_POST
def api_nim_start(request):
    payload = _request_payload(request)
    difficulty = str(payload.get("difficulty") or MathGameSession.DIFFICULTY_MCTS).strip()
    if difficulty not in nim.VALID_DIFFICULTIES:
        difficulty = MathGameSession.DIFFICULTY_MCTS

    session = MathGameSession.objects.create(
        user=_session_owner(request),
        session_key=_ensure_session_key(request),
        game_type=MathGameSession.GAME_NIM,
        difficulty=difficulty,
        state_json=nim.initial_state_json(difficulty),
    )
    MathGameMove.objects.create(
        session=session,
        actor=MathGameMove.ACTOR_SYSTEM,
        move_json={"event": "start"},
        state_json=session.state_json,
        feedback="시작",
    )
    return _response(
        request,
        _nim_public_payload(session, feedback="시작"),
        partial_template="math_games/partials/nim_state.html",
    )


@require_GET
def api_nim_status(request, session_id):
    session = get_object_or_404(MathGameSession, id=session_id, game_type=MathGameSession.GAME_NIM)
    return _response(
        request,
        _nim_public_payload(session),
        partial_template="math_games/partials/nim_state.html",
    )


@require_POST
def api_nim_move(request, session_id):
    session = get_object_or_404(MathGameSession, id=session_id, game_type=MathGameSession.GAME_NIM)
    if session.result != MathGameSession.RESULT_ACTIVE:
        return _response(request, _nim_public_payload(session, feedback="종료"), status=409)

    payload = _request_payload(request)
    history = list(session.state_json.get("history") or [])
    try:
        if "pile_index" in payload:
            pile_index = int(payload.get("pile_index"))
        else:
            pile_index = int(payload.get("pile_number", payload.get("pile"))) - 1
        take = int(payload.get("take"))
        next_history, student_move, state = nim.apply_student_move(history, pile_index, take)
    except (TypeError, ValueError):
        MathGameMove.objects.create(
            session=session,
            actor=MathGameMove.ACTOR_STUDENT,
            move_json={"payload": payload},
            state_json=session.state_json,
            is_valid=False,
            feedback="가져갈 수 없는 수",
        )
        return _response(request, _nim_public_payload(session, feedback="가져갈 수 없는 수"), status=400)

    result = MathGameSession.RESULT_ACTIVE
    feedback = "내 차례"
    ai_move_payload = None
    thought = ""

    MathGameMove.objects.create(
        session=session,
        actor=MathGameMove.ACTOR_STUDENT,
        move_json=student_move,
        state_json=nim.state_to_payload(state, next_history),
        feedback="가져가기",
    )

    if state.is_terminal():
        result = MathGameSession.RESULT_WIN
        feedback = "승리"
    else:
        before_ai_piles = list(getattr(state, "piles", ()))
        ai_action = nim.select_ai_action(session.difficulty or MathGameSession.DIFFICULTY_MCTS, state)
        state.apply_action(ai_action)
        next_history = [*next_history, int(ai_action)]
        ai_move_payload = nim.action_to_payload(ai_action)
        thought = nim.thought_for_move(before_ai_piles, ai_action)
        feedback = "내 차례"
        if state.is_terminal():
            result = MathGameSession.RESULT_LOSE
            feedback = "AI 승리"
        MathGameMove.objects.create(
            session=session,
            actor=MathGameMove.ACTOR_AI,
            move_json=ai_move_payload,
            state_json=nim.state_to_payload(state, next_history, result=result),
            feedback=thought,
        )

    session.state_json = {
        **session.state_json,
        "history": next_history,
        "piles": list(getattr(state, "piles", ())),
        "status": result,
    }
    session.result = result
    if result != MathGameSession.RESULT_ACTIVE:
        session.ended_at = timezone.now()
    session.save(update_fields=["state_json", "result", "ended_at", "updated_at"])

    return _response(
        request,
        _nim_public_payload(session, feedback=feedback, ai_move=ai_move_payload, thought=thought),
        partial_template="math_games/partials/nim_state.html",
    )


@require_POST
def api_twenty_four_start(request):
    puzzle = twenty_four.generate_puzzle(rng=random.Random())
    session = MathGameSession.objects.create(
        user=_session_owner(request),
        session_key=_ensure_session_key(request),
        game_type=MathGameSession.GAME_TWENTY_FOUR,
        difficulty="",
        state_json={
            "numbers": puzzle["numbers"],
            "solution": puzzle["solution"],
            "hints_used": 0,
            "status": MathGameSession.RESULT_ACTIVE,
        },
    )
    MathGameMove.objects.create(
        session=session,
        actor=MathGameMove.ACTOR_SYSTEM,
        move_json={"event": "start"},
        state_json=session.state_json,
        feedback="시작",
    )
    return _response(
        request,
        _twenty_four_payload(session, feedback="시작"),
        partial_template="math_games/partials/twenty_four_state.html",
    )


@require_POST
def api_twenty_four_answer(request, session_id):
    session = get_object_or_404(MathGameSession, id=session_id, game_type=MathGameSession.GAME_TWENTY_FOUR)
    if session.result != MathGameSession.RESULT_ACTIVE:
        return _response(request, _twenty_four_payload(session, feedback="종료"), status=409)

    payload = _request_payload(request)
    expression = str(payload.get("expression") or payload.get("answer") or "").strip()
    numbers = list(session.state_json.get("numbers") or [])

    try:
        checked = twenty_four.validate_answer(expression, numbers)
    except twenty_four.ExpressionError as exc:
        MathGameMove.objects.create(
            session=session,
            actor=MathGameMove.ACTOR_STUDENT,
            move_json={"expression": expression},
            state_json=session.state_json,
            is_valid=False,
            feedback=str(exc),
        )
        return _response(request, _twenty_four_payload(session, feedback=str(exc)), status=400)

    value = checked["value"]
    value_text = str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    if checked["is_correct"]:
        session.result = MathGameSession.RESULT_SOLVED
        session.ended_at = timezone.now()
        session.state_json = {**session.state_json, "status": session.result}
        session.save(update_fields=["result", "ended_at", "state_json", "updated_at"])
        feedback = "정답"
    else:
        feedback = "다시"

    MathGameMove.objects.create(
        session=session,
        actor=MathGameMove.ACTOR_STUDENT,
        move_json={"expression": expression, "value": value_text},
        state_json=session.state_json,
        feedback=feedback,
    )
    return _response(
        request,
        _twenty_four_payload(session, feedback=feedback, value_text=value_text),
        partial_template="math_games/partials/twenty_four_state.html",
    )


@require_POST
def api_twenty_four_hint(request, session_id):
    session = get_object_or_404(MathGameSession, id=session_id, game_type=MathGameSession.GAME_TWENTY_FOUR)
    if session.result != MathGameSession.RESULT_ACTIVE:
        return _response(request, _twenty_four_payload(session, feedback="종료"), status=409)

    state = dict(session.state_json or {})
    hints_used = int(state.get("hints_used") or 0) + 1
    hint = twenty_four.hint_for_solution(str(state.get("solution") or ""), hints_used)
    state["hints_used"] = hints_used
    session.state_json = state
    session.save(update_fields=["state_json", "updated_at"])
    MathGameMove.objects.create(
        session=session,
        actor=MathGameMove.ACTOR_SYSTEM,
        move_json={"event": "hint", "hint_index": hints_used},
        state_json=session.state_json,
        feedback=hint,
    )
    return _response(
        request,
        _twenty_four_payload(session, feedback="힌트", hint=hint),
        partial_template="math_games/partials/twenty_four_state.html",
    )


@require_POST
def api_2048_start(request):
    state = game_2048.initial_state_json(rng=random.Random())
    session = MathGameSession.objects.create(
        user=_session_owner(request),
        session_key=_ensure_session_key(request),
        game_type=MathGameSession.GAME_2048,
        difficulty="",
        state_json={**state, "status": MathGameSession.RESULT_ACTIVE},
    )
    MathGameMove.objects.create(
        session=session,
        actor=MathGameMove.ACTOR_SYSTEM,
        move_json={"event": "start"},
        state_json=session.state_json,
        feedback="시작",
    )
    return _response(request, _game_2048_payload(session, feedback="시작"))


@require_GET
def api_2048_status(request, session_id):
    session = get_object_or_404(MathGameSession, id=session_id, game_type=MathGameSession.GAME_2048)
    return _response(request, _game_2048_payload(session))


@require_POST
def api_2048_move(request, session_id):
    session = get_object_or_404(MathGameSession, id=session_id, game_type=MathGameSession.GAME_2048)
    if session.result != MathGameSession.RESULT_ACTIVE:
        return _response(request, _game_2048_payload(session, feedback="종료"), status=409)

    payload = _request_payload(request)
    direction = str(payload.get("direction") or "").strip().lower()
    try:
        state = game_2048.apply_move(session.state_json, direction, rng=random.Random())
    except game_2048.InvalidDirection:
        MathGameMove.objects.create(
            session=session,
            actor=MathGameMove.ACTOR_STUDENT,
            move_json={"payload": payload},
            state_json=session.state_json,
            is_valid=False,
            feedback="방향 확인",
        )
        return _response(request, _game_2048_payload(session, feedback="방향 확인"), status=400)

    result = MathGameSession.RESULT_ACTIVE
    feedback = "이동"
    if state["won"]:
        result = MathGameSession.RESULT_WIN
        feedback = "2048"
    elif state["game_over"]:
        result = MathGameSession.RESULT_LOSE
        feedback = "끝"
    elif not state["moved"]:
        feedback = "막힘"
    elif state["gained"]:
        feedback = f"+{state['gained']}"

    session.state_json = {**state, "status": result}
    session.result = result
    if result != MathGameSession.RESULT_ACTIVE:
        session.ended_at = timezone.now()
    session.save(update_fields=["state_json", "result", "ended_at", "updated_at"])

    MathGameMove.objects.create(
        session=session,
        actor=MathGameMove.ACTOR_STUDENT,
        move_json={
            "direction": direction,
            "moved": state["moved"],
            "gained": state["gained"],
            "spawned": state["spawned"],
        },
        state_json=session.state_json,
        feedback=feedback,
    )
    return _response(request, _game_2048_payload(session, feedback=feedback))
