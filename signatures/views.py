from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import TrainingSession, Signature
from .forms import TrainingSessionForm, SignatureForm


@login_required
def session_list(request):
    """내가 만든 연수 목록"""
    sessions = TrainingSession.objects.filter(created_by=request.user)
    return render(request, 'signatures/list.html', {'sessions': sessions})


@login_required
def session_create(request):
    """연수 생성"""
    if request.method == 'POST':
        form = TrainingSessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.created_by = request.user
            session.save()
            messages.success(request, '연수가 생성되었습니다.')
            return redirect('signatures:detail', uuid=session.uuid)
    else:
        form = TrainingSessionForm()
    return render(request, 'signatures/create.html', {'form': form})


@login_required
def session_detail(request, uuid):
    """연수 상세 (관리자용)"""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    signatures = session.signatures.all()
    return render(request, 'signatures/detail.html', {
        'session': session,
        'signatures': signatures,
    })


@login_required
def session_edit(request, uuid):
    """연수 수정"""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    if request.method == 'POST':
        form = TrainingSessionForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, '연수 정보가 수정되었습니다.')
            return redirect('signatures:detail', uuid=session.uuid)
    else:
        form = TrainingSessionForm(instance=session)
    return render(request, 'signatures/edit.html', {'form': form, 'session': session})


@login_required
def session_delete(request, uuid):
    """연수 삭제"""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    if request.method == 'POST':
        session.delete()
        messages.success(request, '연수가 삭제되었습니다.')
        return redirect('signatures:list')
    return render(request, 'signatures/delete_confirm.html', {'session': session})


def sign(request, uuid):
    """서명 페이지 (공개 - 로그인 불필요)"""
    session = get_object_or_404(TrainingSession, uuid=uuid)

    if not session.is_active:
        return render(request, 'signatures/closed.html', {'session': session})

    if request.method == 'POST':
        form = SignatureForm(request.POST)
        if form.is_valid():
            signature = form.save(commit=False)
            signature.training_session = session
            signature.save()
            return render(request, 'signatures/sign_success.html', {'session': session})
    else:
        form = SignatureForm()

    return render(request, 'signatures/sign.html', {
        'session': session,
        'form': form,
    })


@login_required
def print_view(request, uuid):
    """출석부 인쇄 페이지 (2단 구성)"""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    signatures = list(session.signatures.all())
    
    # 2단 구성을 위해 리스트 분할 (최대 60명 기준, 넘어가면 페이지 분할은 나중에)
    left_sigs = signatures[:30]
    right_sigs = signatures[30:60]
    
    # 빈 줄 생성을 위한 숫자 리스트
    left_rows = range(30)
    right_rows = range(31, 61)
    
    return render(request, 'signatures/print_view.html', {
        'session': session,
        'left_sigs': left_sigs,
        'right_sigs': right_sigs,
        'left_rows': left_rows,
        'right_rows': right_rows,
        'total_count': len(signatures),
    })


@login_required
@require_POST
def toggle_active(request, uuid):
    """서명 받기 활성화/비활성화 토글 (AJAX)"""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    session.is_active = not session.is_active
    session.save()
    return JsonResponse({
        'success': True,
        'is_active': session.is_active,
    })


@login_required
@require_POST
def delete_signature(request, pk):
    """개별 서명 삭제 (AJAX)"""
    signature = get_object_or_404(Signature, pk=pk, training_session__created_by=request.user)
    signature.delete()
    return JsonResponse({'success': True})
