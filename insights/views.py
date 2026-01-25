from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import DetailView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Insight
from .forms import InsightForm

def insight_list(request):
    from django.db.models import Count

    # 정렬 파라미터 처리
    sort = request.GET.get('sort', 'recent')

    insights = Insight.objects.all()

    if sort == 'recent':
        insights = insights.order_by('-created_at')
    elif sort == 'oldest':
        insights = insights.order_by('created_at')
    elif sort == 'popular':
        insights = insights.annotate(likes_count=Count('likes')).order_by('-likes_count', '-created_at')

    return render(request, 'insights/insight_list.html', {
        'insights': insights,
        'current_sort': sort
    })

class InsightDetailView(DetailView):
    model = Insight
    template_name = 'insights/insight_detail.html'
    context_object_name = 'insight'

@login_required
def insight_create(request):
    if request.method == 'POST':
        form = InsightForm(request.POST)
        if form.is_valid():
            insight = form.save()
            messages.success(request, '인사이트가 성공적으로 등록되었습니다!')
            return redirect('insights:detail', pk=insight.pk)
    else:
        form = InsightForm()

    return render(request, 'insights/insight_form.html', {
        'form': form,
        'title': '새 인사이트 등록'
    })

@login_required
def insight_update(request, pk):
    insight = get_object_or_404(Insight, pk=pk)

    if request.method == 'POST':
        form = InsightForm(request.POST, instance=insight)
        if form.is_valid():
            form.save()
            messages.success(request, '인사이트가 성공적으로 수정되었습니다!')
            return redirect('insights:detail', pk=insight.pk)
    else:
        form = InsightForm(instance=insight)

    return render(request, 'insights/insight_form.html', {
        'form': form,
        'title': '인사이트 수정',
        'insight': insight
    })

@login_required
def insight_like_toggle(request, pk):
    """AJAX 좋아요 토글"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    insight = get_object_or_404(Insight, pk=pk)
    user = request.user

    if user in insight.likes.all():
        insight.likes.remove(user)
        liked = False
    else:
        insight.likes.add(user)
        liked = True

    return JsonResponse({
        'liked': liked,
        'total_likes': insight.total_likes
    })
