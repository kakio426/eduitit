from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import DetailView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count
from django.core.exceptions import ValidationError
from .models import Insight
from .forms import InsightForm, InsightPasteForm
from .importer import upsert_insight_from_text


def insight_list(request):
    """인사이트 목록 — 카테고리/태그/정렬 필터 지원"""
    sort = request.GET.get('sort', 'recent')
    category = request.GET.get('category', '')
    tag = request.GET.get('tag', '')

    # featured 인사이트 (상단 고정)
    featured_insights = Insight.objects.filter(is_featured=True).annotate(
        likes_count_annotated=Count('likes', distinct=True)
    ).order_by('-created_at')

    # 일반 목록 (featured 제외)
    insights = Insight.objects.filter(is_featured=False).annotate(
        likes_count_annotated=Count('likes', distinct=True)
    )

    # 카테고리 필터
    if category:
        insights = insights.filter(category=category)

    # 태그 필터
    if tag:
        insights = insights.filter(tags__icontains=tag)
        featured_insights = featured_insights.filter(tags__icontains=tag)

    # 정렬
    if sort == 'recent':
        insights = insights.order_by('-created_at')
    elif sort == 'oldest':
        insights = insights.order_by('created_at')
    elif sort == 'popular':
        insights = insights.order_by('-likes_count_annotated', '-created_at')

    return render(request, 'insights/insight_list.html', {
        'insights': insights,
        'featured_insights': featured_insights,
        'current_sort': sort,
        'current_category': category,
        'current_tag': tag,
    })


class InsightDetailView(DetailView):
    model = Insight
    template_name = 'insights/insight_detail.html'
    context_object_name = 'insight'

    def get_queryset(self):
        return Insight.objects.annotate(
            likes_count_annotated=Count('likes', distinct=True)
        )


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
def insight_paste_create(request):
    if request.method == 'POST':
        form = InsightPasteForm(request.POST)
        if form.is_valid():
            try:
                insight, created = upsert_insight_from_text(form.cleaned_data['raw_text'])
            except ValueError as exc:
                form.add_error('raw_text', str(exc))
            except ValidationError as exc:
                form.add_error(None, "; ".join(exc.messages))
            else:
                if created:
                    messages.success(request, '붙여넣기 내용으로 인사이트가 등록되었습니다.')
                else:
                    messages.success(request, '같은 영상 URL 항목을 찾아 인사이트를 업데이트했습니다.')
                return redirect('insights:detail', pk=insight.pk)
    else:
        form = InsightPasteForm()

    return render(request, 'insights/insight_paste_form.html', {
        'form': form,
        'title': '붙여넣기 등록',
    })


@login_required
def insight_update(request, pk):
    insight = get_object_or_404(Insight, pk=pk)
    if not request.user.is_superuser:
        messages.error(request, '수정 권한이 없습니다.')
        return redirect('insights:detail', pk=insight.pk)

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
def insight_delete(request, pk):
    """인사이트 삭제 — POST 전용, superuser 전용"""
    if not request.user.is_superuser:
        messages.error(request, '삭제 권한이 없습니다.')
        return redirect('insights:list')

    if request.method != 'POST':
        return redirect('insights:list')

    insight = get_object_or_404(Insight, pk=pk)
    insight.delete()
    messages.success(request, '인사이트가 삭제되었습니다.')
    return redirect('insights:list')


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
        'total_likes': insight.likes.count()
    })
