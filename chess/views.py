from django.shortcuts import render


def _student_games_mode(request):
    return bool(request.session.get("dutyticker_student_games_mode"))


def index(request):
    """체스 메인 로비 페이지"""
    return render(request, 'chess/index.html', {'hide_navbar': _student_games_mode(request)})


def rules(request):
    """체스 규칙 가이드 페이지"""
    return render(request, 'chess/rules.html', {'hide_navbar': _student_games_mode(request)})


def play(request):
    """체스 게임 플레이 페이지"""
    # URL 파라미터로 게임 모드와 난이도 받기
    mode = request.GET.get('mode', 'local')  # local 또는 ai
    difficulty = request.GET.get('difficulty', 'medium')  # easy, medium, hard, expert

    context = {
        'mode': mode,
        'difficulty': difficulty,
        'hide_navbar': _student_games_mode(request),
    }
    return render(request, 'chess/play.html', context)
