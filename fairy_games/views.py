from django.http import Http404
from django.shortcuts import render

from core.seo import build_route_page_seo

from .game_catalog import GAME_CATALOG

CANONICAL_PLAY_ROUTE_NAMES = {
    "dobutsu": "fairy_games:play_dobutsu",
    "cfour": "fairy_games:play_cfour",
    "isolation": "fairy_games:play_isolation",
    "ataxx": "fairy_games:play_ataxx",
    "breakthrough": "fairy_games:play_breakthrough",
    "reversi": "fairy_games:play_reversi",
}


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
        {
            "games": games,
            "hide_navbar": _student_games_mode(request),
            **build_route_page_seo(
                request,
                title="전략 게임 6종 - Eduitit",
                description="동물 장기, 커넥트 포, 리버시 등 교실에서 바로 즐길 수 있는 전략 게임 모음입니다.",
                route_name="fairy_games:index",
            ).as_context(),
        },
    )


def rules(request, variant):
    game = GAME_CATALOG.get(variant)
    if not game:
        raise Http404("Unknown game variant")
    return render(
        request,
        "fairy_games/rules.html",
        {
            "variant": variant,
            "game": game,
            "hide_navbar": _student_games_mode(request),
            **build_route_page_seo(
                request,
                title=f"{game['title']} 규칙 - Eduitit",
                description=f"{game['subtitle']} {game['goal']}",
                route_name="fairy_games:rules",
                route_kwargs={"variant": variant},
            ).as_context(),
        },
    )


def play(request, variant):
    game = GAME_CATALOG.get(variant)
    if not game:
        raise Http404("Unknown game variant")

    # 전략 게임 6종은 현재 로컬 대결만 지원
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
            **build_route_page_seo(
                request,
                title=f"{game['title']} 플레이 - Eduitit",
                description=f"{game['subtitle']} 지금 바로 {game['title']}를 플레이해 보세요.",
                route_name=CANONICAL_PLAY_ROUTE_NAMES.get(variant, "fairy_games:play"),
                route_kwargs={} if variant in CANONICAL_PLAY_ROUTE_NAMES else {"variant": variant},
            ).as_context(),
        },
    )
