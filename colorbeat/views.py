from django.shortcuts import render

from core.seo import build_route_page_seo


def _student_games_mode(request):
    return bool(request.session.get("dutyticker_student_games_mode"))


def main(request):
    return render(
        request,
        "colorbeat/main.html",
        {
            "hide_navbar": _student_games_mode(request),
            **build_route_page_seo(
                request,
                title="알록달록 비트메이커 - Eduitit",
                description="칸을 눌러 리듬을 만들고 바로 들어 보는 교실 음악 코딩 활동입니다.",
                route_name="colorbeat:main",
            ).as_context(),
        },
    )
