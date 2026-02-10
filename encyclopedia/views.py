from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import NotebookEntry
from .forms import NotebookEntryForm


def landing(request):
    """서비스 소개 + 목록 페이지 (비로그인도 볼 수 있음)"""
    from products.models import Product
    service = Product.objects.filter(title='교사 백과사전').first()
    entries = NotebookEntry.objects.filter(is_active=True).select_related('creator')
    form = NotebookEntryForm()

    return render(request, 'encyclopedia/landing.html', {
        'service': service,
        'entries': entries,
        'form': form,
    })


@login_required
def entry_create(request):
    """새 NotebookLM 항목 등록"""
    if request.method != 'POST':
        return redirect('encyclopedia:landing')

    form = NotebookEntryForm(request.POST)
    if form.is_valid():
        entry = form.save(commit=False)
        entry.creator = request.user
        entry.save()
        messages.success(request, '백과사전이 등록되었습니다!')
        return redirect('encyclopedia:landing')

    # 폼 에러 시 다시 렌더링
    from products.models import Product
    service = Product.objects.filter(title='교사 백과사전').first()
    entries = NotebookEntry.objects.filter(is_active=True).select_related('creator')
    return render(request, 'encyclopedia/landing.html', {
        'service': service,
        'entries': entries,
        'form': form,
    })


@login_required
def entry_edit(request, pk):
    """항목 수정 (작성자 본인만)"""
    entry = get_object_or_404(NotebookEntry, pk=pk)
    if entry.creator != request.user and not request.user.is_superuser:
        messages.error(request, '본인이 등록한 항목만 수정할 수 있습니다.')
        return redirect('encyclopedia:landing')

    if request.method == 'POST':
        form = NotebookEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, '수정되었습니다!')
            return redirect('encyclopedia:landing')
    else:
        form = NotebookEntryForm(instance=entry)

    return render(request, 'encyclopedia/edit.html', {
        'form': form,
        'entry': entry,
    })


@login_required
def entry_delete(request, pk):
    """항목 삭제 (작성자 본인만)"""
    entry = get_object_or_404(NotebookEntry, pk=pk)
    if entry.creator != request.user and not request.user.is_superuser:
        messages.error(request, '본인이 등록한 항목만 삭제할 수 있습니다.')
        return redirect('encyclopedia:landing')

    if request.method == 'POST':
        entry.delete()
        messages.success(request, '삭제되었습니다!')

    return redirect('encyclopedia:landing')
