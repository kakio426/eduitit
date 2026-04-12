from django.shortcuts import render

from core.seo import build_route_page_seo


def _student_games_mode(request):
    return bool(request.session.get("dutyticker_student_games_mode"))


def index(request):
    return render(
        request,
        'janggi/index.html',
        {
            'hide_navbar': _student_games_mode(request),
            **build_route_page_seo(
                request,
                title="교실 장기 - Eduitit",
                description="교실에서 바로 둘 수 있는 장기 게임 랜딩입니다.",
                route_name="janggi:index",
            ).as_context(),
        },
    )


def rules(request):
    return render(
        request,
        'janggi/rules.html',
        {
            'hide_navbar': _student_games_mode(request),
            **build_route_page_seo(
                request,
                title="장기 규칙 - Eduitit",
                description="장기 말의 이동과 기본 규칙을 빠르게 익히는 안내 페이지입니다.",
                route_name="janggi:rules",
            ).as_context(),
        },
    )


def play(request):
    mode = request.GET.get('mode', 'local')
    if mode != 'ai':
        mode = 'local'
    context = {
        'mode': mode,
        'hide_navbar': _student_games_mode(request),
        **build_route_page_seo(
            request,
            title="장기 플레이 - Eduitit",
            description="한 화면에서 장기를 바로 둘 수 있는 플레이 화면입니다.",
            route_name="janggi:play",
        ).as_context(),
    }
    return render(request, 'janggi/play.html', context)
