from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import DetailView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count
from django.core.exceptions import ValidationError
from django.urls import reverse
from core.seo import build_insight_detail_seo, build_insight_list_seo
from .models import Insight
from .forms import InsightForm, InsightPasteForm
from .importer import upsert_insight_from_text


def _apply_insight_filters(queryset, *, track="", category="", tag=""):
    if track:
        queryset = queryset.filter(track=track)
    if category:
        queryset = queryset.filter(category=category)
    if tag:
        queryset = queryset.filter(tags__icontains=tag)
    return queryset


def _order_insights(queryset, sort):
    if sort == 'oldest':
        return queryset.order_by('created_at')
    if sort == 'popular':
        return queryset.order_by('-likes_count_annotated', '-created_at')
    return queryset.order_by('-created_at')


def _build_related_insights(insight):
    queryset = Insight.objects.annotate(
        likes_count_annotated=Count('likes', distinct=True)
    ).exclude(pk=insight.pk)
    if insight.series_name:
        related = queryset.filter(series_name=insight.series_name).order_by('-created_at')[:3]
        if related:
            return related
    if insight.track:
        related = queryset.filter(track=insight.track).order_by('-is_featured', '-created_at')[:3]
        if related:
            return related
    return queryset.order_by('-is_featured', '-created_at')[:3]


def _build_related_tool_links(insight):
    if insight.track == 'classroom':
        return [
            {
                'label': '수업 준비',
                'description': '바로 수업에 옮길 자료와 흐름을 정리합니다.',
                'href': reverse('prompt_lab'),
            },
            {
                'label': '포트폴리오',
                'description': '현장 적용 사례를 더 이어서 봅니다.',
                'href': reverse('portfolio:list'),
            },
        ]
    if insight.track == 'editorial':
        return [
            {
                'label': 'AI 법률 가이드',
                'description': '운영 기준과 판단 포인트를 함께 확인합니다.',
                'href': reverse('teacher_law:main'),
            },
            {
                'label': '프롬프트 연구실',
                'description': '다음 문장과 질문을 바로 꺼내 씁니다.',
                'href': reverse('prompt_lab'),
            },
        ]
    return [
        {
            'label': '알림장 멘트',
            'description': '읽은 내용을 바로 안내문과 멘트로 옮깁니다.',
            'href': reverse('noticegen:main'),
        },
        {
            'label': '잇티수합',
            'description': '가정 응답과 자료 수합 흐름으로 바로 이어갑니다.',
            'href': reverse('collect:landing'),
        },
    ]


def insight_list(request):
    """인사이트 목록 — 카테고리/태그/정렬 필터 지원"""
    sort = request.GET.get('sort', 'recent')
    track = request.GET.get('track', '')
    category = request.GET.get('category', '')
    tag = request.GET.get('tag', '')

    featured_queryset = Insight.objects.filter(is_featured=True).annotate(
        likes_count_annotated=Count('likes', distinct=True)
    )
    insight_queryset = Insight.objects.filter(is_featured=False).annotate(
        likes_count_annotated=Count('likes', distinct=True)
    )

    featured_queryset = _apply_insight_filters(
        featured_queryset,
        track=track,
        category=category,
        tag=tag,
    ).order_by('-created_at')
    insight_queryset = _apply_insight_filters(
        insight_queryset,
        track=track,
        category=category,
        tag=tag,
    )
    insight_queryset = _order_insights(insight_queryset, sort)

    featured_insights = list(featured_queryset[:4])
    featured_primary = featured_insights[0] if featured_insights else None
    featured_secondary = featured_insights[1:]
    if featured_primary is None:
        featured_primary = insight_queryset.first()
        if featured_primary is not None:
            insight_queryset = insight_queryset.exclude(pk=featured_primary.pk)

    return render(request, 'insights/insight_list.html', {
        'insights': insight_queryset,
        'featured_insights': featured_insights,
        'featured_primary': featured_primary,
        'featured_secondary': featured_secondary,
        'track_choices': Insight.TRACK_CHOICES,
        'current_track': track,
        'current_sort': sort,
        'current_category': category,
        'current_tag': tag,
        **build_insight_list_seo(
            request,
            current_track=track,
            current_category=category,
            current_tag=tag,
            current_sort=sort,
        ).as_context(),
    })


class InsightDetailView(DetailView):
    model = Insight
    template_name = 'insights/insight_detail.html'
    context_object_name = 'insight'

    def get_queryset(self):
        return Insight.objects.annotate(
            likes_count_annotated=Count('likes', distinct=True)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_insights'] = _build_related_insights(self.object)
        context['related_tool_links'] = _build_related_tool_links(self.object)
        context.update(build_insight_detail_seo(self.request, self.object).as_context())
        return context


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
    if not request.user.is_superuser:
        messages.error(request, '붙여넣기 등록 권한이 없습니다.')
        return redirect('insights:list')

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
