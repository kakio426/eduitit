from django.shortcuts import render


def _student_games_mode(request):
    return bool(request.session.get("dutyticker_student_games_mode"))


def index(request):
    return render(request, 'janggi/index.html', {'hide_navbar': _student_games_mode(request)})


def rules(request):
    return render(request, 'janggi/rules.html', {'hide_navbar': _student_games_mode(request)})


def play(request):
    mode = request.GET.get('mode', 'local')
    if mode != 'ai':
        mode = 'local'
    context = {
        'mode': mode,
        'hide_navbar': _student_games_mode(request),
    }
    return render(request, 'janggi/play.html', context)
