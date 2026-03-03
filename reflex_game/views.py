from django.shortcuts import render


def _student_games_mode(request):
    return bool(request.session.get("dutyticker_student_games_mode"))


def main(request):
    return render(
        request,
        "reflex_game/main.html",
        {
            "hide_navbar": _student_games_mode(request),
        },
    )

