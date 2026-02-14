from django.shortcuts import render


def index(request):
    return render(request, 'janggi/index.html')


def rules(request):
    return render(request, 'janggi/rules.html')


def play(request):
    mode = request.GET.get('mode', 'local')
    difficulty = request.GET.get('difficulty', 'medium')
    context = {
        'mode': mode,
        'difficulty': difficulty,
    }
    return render(request, 'janggi/play.html', context)

