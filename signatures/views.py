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
    """출석부 인쇄 페이지 (자동 페이지 분할 지원)"""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    signatures = list(session.signatures.all())
    total_count = len(signatures)
    
    # 페이지당 60명씩 분할
    SIGS_PER_PAGE = 60
    pages = []
    
    # 60명 단위로 페이지 생성
    for page_num in range(0, total_count, SIGS_PER_PAGE):
        page_sigs = signatures[page_num:page_num + SIGS_PER_PAGE]
        
        # 각 페이지를 좌우 30명씩 분할
        left_sigs = page_sigs[:30]
        right_sigs = page_sigs[30:60]
        
        # 빈 줄 생성 (30줄 고정, 순번은 절대 위치 기준)
        left_rows = range(page_num + 1, page_num + 31)
        right_rows = range(page_num + 31, page_num + 61)
        
        pages.append({
            'page_number': (page_num // SIGS_PER_PAGE) + 1,
            'left_sigs': left_sigs,
            'right_sigs': right_sigs,
            'left_rows': left_rows,
            'right_rows': right_rows,
        })
    
    return render(request, 'signatures/print_view.html', {
        'session': session,
        'pages': pages,
        'total_count': total_count,
        'total_pages': len(pages),
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
@login_required
def style_list(request):
    """내 서명 스타일 즐겨찾기 목록"""
    from .models import SignatureStyle
    styles = SignatureStyle.objects.filter(user=request.user)
    return render(request, 'signatures/style_list.html', {'styles': styles})


@login_required
@require_POST
def save_style_api(request):
    """스타일 즐겨찾기 저장 API"""
    import json
    try:
        data = json.loads(request.body)
        from .models import SignatureStyle, SavedSignature
        
        # 스타일 저장
        SignatureStyle.objects.create(
            user=request.user,
            name=data.get('name', '내 서명 스타일'),
            font_family=data.get('font_family'),
            color=data.get('color'),
            background_color=data.get('background_color')
        )

        # 이미지 데이터가 있으면 별도 저장 (선택)
        if data.get('image_data'):
            SavedSignature.objects.create(
                user=request.user,
                image_data=data.get('image_data')
            )
            
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def save_signature_image_api(request):
    """서명 이미지 저장 API (스타일 없이 이미지만)"""
    import json
    try:
        data = json.loads(request.body)
        from .models import SavedSignature
        SavedSignature.objects.create(
            user=request.user,
            image_data=data.get('image_data')
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def get_my_signatures_api(request):
    """내 저장된 서명 이미지 목록 가져오기"""
    from .models import SavedSignature
    signatures = SavedSignature.objects.filter(user=request.user).order_by('-created_at')[:5]
    data = [{'id': sig.id, 'image_data': sig.image_data} for sig in signatures]
    return JsonResponse({'signatures': data})


@login_required
@require_POST
def delete_style_api(request, pk):
    """스타일 삭제"""
    from .models import SignatureStyle
    style = get_object_or_404(SignatureStyle, pk=pk, user=request.user)
    style.delete()
    return JsonResponse({'success': True})


def signature_maker(request):
    """전자 서명 제작 도구 (비회원 개방)"""
    # 추천 폰트 리스트
    fonts = [
        'Nanum Brush Script', 'Nanum Pen Script', 'Cafe24 Ssurround Air', 
        'Gowun Batang', 'Gamja Flower', 'Poor Story'
    ]
    return render(request, 'signatures/maker.html', {
        'fonts': fonts,
        'is_guest': not request.user.is_authenticated
    })
