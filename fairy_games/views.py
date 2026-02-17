from django.http import Http404
from django.shortcuts import render

from .game_catalog import GAME_CATALOG


def index(request):
    games = []
    for key, value in GAME_CATALOG.items():
        game = {"key": key}
        game.update(value)
        games.append(game)
    return render(request, "fairy_games/index.html", {"games": games})


def rules(request, variant):
    game = GAME_CATALOG.get(variant)
    if not game:
        raise Http404("Unknown game variant")
    return render(
        request,
        "fairy_games/rules.html",
        {"variant": variant, "game": game},
    )


def play(request, variant):
    game = GAME_CATALOG.get(variant)
    if not game:
        raise Http404("Unknown game variant")

    mode = request.GET.get("mode", "local")
    if mode not in ("local", "ai"):
        mode = "local"

    difficulty = request.GET.get("difficulty", "medium")
    if difficulty not in ("easy", "medium", "hard", "expert"):
        difficulty = "medium"

    return render(
        request,
        "fairy_games/play.html",
        {
            "variant": variant,
            "game": game,
            "mode": mode,
            "difficulty": difficulty,
        },
    )

