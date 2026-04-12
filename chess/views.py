from django.shortcuts import render

from core.seo import build_route_page_seo


def _student_games_mode(request):
    return bool(request.session.get("dutyticker_student_games_mode"))


def index(request):
    """체스 메인 로비 페이지"""
    return render(
        request,
        'chess/index.html',
        {
            'hide_navbar': _student_games_mode(request),
            **build_route_page_seo(
                request,
                title="체스 게임 - Eduitit",
                description="교실이나 쉬는 시간에 바로 시작할 수 있는 체스 게임 랜딩입니다.",
                route_name="chess:index",
            ).as_context(),
        },
    )


def rules(request):
    """체스 규칙 가이드 페이지"""
    return render(
        request,
        'chess/rules.html',
        {
            'hide_navbar': _student_games_mode(request),
            **build_route_page_seo(
                request,
                title="체스 규칙 - Eduitit",
                description="체스 말의 이동과 기본 승리 조건을 빠르게 익힐 수 있는 규칙 안내입니다.",
                route_name="chess:rules",
            ).as_context(),
        },
    )


def play(request):
    """체스 게임 플레이 페이지"""
    # URL 파라미터로 게임 모드와 난이도 받기
    mode = request.GET.get('mode', 'local')  # local 또는 ai
    difficulty = request.GET.get('difficulty', 'medium')  # easy, medium, hard, expert

    context = {
        'mode': mode,
        'difficulty': difficulty,
        'hide_navbar': _student_games_mode(request),
        **build_route_page_seo(
            request,
            title="체스 플레이 - Eduitit",
            description="로컬 대전 또는 AI 대전으로 체스를 바로 플레이할 수 있는 게임 화면입니다.",
            route_name="chess:play",
        ).as_context(),
    }
    return render(request, 'chess/play.html', context)
