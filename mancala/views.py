import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from core.seo import build_route_page_seo

from .engine import MancalaInputError, initial_response, play_move


STUDENT_GAMES_SESSION_KEY = "dutyticker_student_games_mode"


def _student_games_mode(request):
    return bool(request.session.get(STUDENT_GAMES_SESSION_KEY))


def main(request):
    initial_payload = initial_response()
    return render(
        request,
        "mancala/main.html",
        {
            "hide_navbar": _student_games_mode(request),
            "initial_payload": initial_payload,
            **build_route_page_seo(
                request,
                title="만칼라 - Eduitit",
                description="분배와 셈을 3D 보드에서 바로 익히는 교실 만칼라 게임입니다.",
                route_name="mancala:main",
            ).as_context(),
        },
    )


@require_GET
def api_state(request):
    return JsonResponse(initial_response())


@require_POST
def api_move(request):
    try:
        payload = _json_body(request)
        response = play_move(
            payload.get("history"),
            payload.get("action"),
            mode=payload.get("mode", "ai"),
        )
    except MancalaInputError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON 형식이 아닙니다."}, status=400)
    return JsonResponse(response)


def _json_body(request):
    if not request.body:
        return {}
    decoded = request.body.decode("utf-8")
    payload = json.loads(decoded)
    if not isinstance(payload, dict):
        raise MancalaInputError("JSON 객체여야 합니다.")
    return payload
