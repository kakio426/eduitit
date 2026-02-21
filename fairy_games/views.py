from django.http import Http404
from django.shortcuts import render

from .game_catalog import GAME_CATALOG


def _student_games_mode(request):
    return bool(request.session.get("dutyticker_student_games_mode"))


def index(request):
    games = []
    for key, value in GAME_CATALOG.items():
        game = {"key": key}
        game.update(value)
        games.append(game)
    return render(
        request,
        "fairy_games/index.html",
        {"games": games, "hide_navbar": _student_games_mode(request)},
    )


def rules(request, variant):
    game = GAME_CATALOG.get(variant)
    if not game:
        raise Http404("Unknown game variant")
    return render(
        request,
        "fairy_games/rules.html",
        {"variant": variant, "game": game, "hide_navbar": _student_games_mode(request)},
    )


def play(request, variant):
    game = GAME_CATALOG.get(variant)
    if not game:
        raise Http404("Unknown game variant")

    # 전략 게임 5종은 현재 로컬 대결만 지원
    mode = "local"
    difficulty = "none"

    return render(
        request,
        "fairy_games/play.html",
        {
            "variant": variant,
            "game": game,
            "mode": mode,
            "difficulty": difficulty,
            "hide_navbar": _student_games_mode(request),
        },
    )
