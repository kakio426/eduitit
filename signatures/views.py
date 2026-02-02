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
    """연수 상세 (관리자용) - 미매칭 및 중복 감지 포함"""
    from .models import ExpectedParticipant
    from collections import defaultdict
    from django.http import HttpResponse
    import traceback
    
    try:
        session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
        signatures = session.signatures.all()
        expected = session.expected_participants.all()
        
        # 1. 미매칭 서명 찾기 (명단이 있는 경우에만 수행)
        suggestions = []
        if expected.exists():
            matched_sig_ids = expected.filter(
                matched_signature__isnull=False
            ).values_list('matched_signature_id', flat=True)
            
            unmatched_signatures = signatures.exclude(id__in=matched_sig_ids)
            
            # 각 미매칭 서명에 대해 정확히 일치하는 예상 참석자 찾기
            for sig in unmatched_signatures:
                exact_matches = expected.filter(
                    name=sig.participant_name,
                    matched_signature__isnull=True
                )
                
                suggestions.append({
                    'signature': sig,
                    'exact_matches': list(exact_matches),
                    'has_matches': exact_matches.exists(),
                })
        
        # 3. 중복 서명 감지 (항상 수행)
        sig_dict = defaultdict(list)
        for sig in signatures:
            key = (sig.participant_name, sig.participant_affiliation or '')
            sig_dict[key].append(sig)
        
        duplicates = [sigs for sigs in sig_dict.values() if len(sigs) > 1]
        
        return render(request, 'signatures/detail.html', {
            'session': session,
            'signatures': signatures,
            'expected_participants': expected,
            'unmatched_suggestions': suggestions,
            'duplicates': duplicates,
            'has_unmatched': len(suggestions) > 0,
            'has_duplicates': len(duplicates) > 0,
        })
    except Exception as e:
        traceback.print_exc()
        return HttpResponse(f"Server Error in session_detail: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status=500)



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
    """출석부 인쇄 페이지 - 명단 유무에 따라 동작 변경"""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    
    # 데이터 준비
    print_items = []
    signed_count = 0
    
    if session.expected_participants.exists():
        # Case A: 명단이 있는 경우 (Phase 2) -> 명단 기준 + 미매칭 서명
        participants = session.expected_participants.all().order_by('name')
        
        # 1. 예상 참석자 추가
        for p in participants:
            item = {
                'name': p.name,
                'affiliation': p.affiliation,
                'signature_data': p.matched_signature.signature_data if p.matched_signature else None
            }
            print_items.append(item)
            if item['signature_data']:
                signed_count += 1
                
        # 2. 명단에 없는 추가 서명(Walk-ins) 추가
        matched_sig_ids = [p.matched_signature.id for p in participants if p.matched_signature]
        unmatched_sigs = session.signatures.exclude(id__in=matched_sig_ids)
        
        for sig in unmatched_sigs:
            print_items.append({
                'name': sig.participant_name,
                'affiliation': sig.participant_affiliation,
                'signature_data': sig.signature_data
            })
            signed_count += 1
            
        total_expected = session.expected_count or len(participants)
        
    else:
        # Case B: 명단이 없는 경우 (Phase 1) -> 서명 기준
        signatures = session.signatures.all().order_by('participant_name')
        for sig in signatures:
            print_items.append({
                'name': sig.participant_name,
                'affiliation': sig.participant_affiliation,
                'signature_data': sig.signature_data
            })
        signed_count = len(print_items)
        total_expected = session.expected_count or signed_count
    
    # 페이지네이션 처리
    total_items = len(print_items)
    SIGS_PER_PAGE = 60
    pages = []
    
    for page_num in range(0, total_items, SIGS_PER_PAGE):
        # 이번 페이지의 아이템들 (최대 60개)
        page_items = print_items[page_num:page_num + SIGS_PER_PAGE]
        
        # 좌우 분할 (30개씩)
        left_items = page_items[:30]
        right_items = page_items[30:60]
        
        # 빈 줄 채우기 (항상 30줄이 되도록)
        # left_rows/right_rows는 순번만 계산
        current_base_idx = page_num
        
        pages.append({
            'page_number': (page_num // SIGS_PER_PAGE) + 1,
            'left_items': left_items,
            'right_items': right_items,
            'left_start_index': current_base_idx + 1,
            'right_start_index': current_base_idx + 31,
            'left_padding': range(30 - len(left_items)),
            'right_padding': range(30 - len(right_items)),
        })
    
    # 페이지가 하나도 없으면 빈 페이지 하나 생성
    if not pages:
        pages.append({
            'page_number': 1,
            'left_items': [], 'right_items': [],
            'left_start_index': 1, 'right_start_index': 31,
            'left_padding': range(30), 'right_padding': range(30)
        })

    return render(request, 'signatures/print_view.html', {
        'session': session,
        'pages': pages,
        'total_count': total_expected,
        'signed_count': signed_count,
        'unsigned_count': max(0, total_expected - signed_count),
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


# ===== Phase 2: Expected Participants Management =====

@login_required
@require_POST
def add_expected_participants(request, uuid):
    """예상 참석자 명단 일괄 등록"""
    from .models import ExpectedParticipant
    import json
    
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    
    try:
        data = json.loads(request.body)
        participants_text = data.get('participants', '')
        
        if not participants_text.strip():
            return JsonResponse({'success': False, 'error': '명단이 비어있습니다.'})
        
        # Parse input (format: "이름, 소속" or "이름")
        lines = participants_text.strip().split('\n')
        created_count = 0
        skipped_count = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            parts = [p.strip() for p in line.split(',')]
            name = parts[0] if parts else ''
            affiliation = parts[1] if len(parts) > 1 else ''
            
            if not name:
                skipped_count += 1
                continue
            
            # Create or skip if duplicate
            _, created = ExpectedParticipant.objects.get_or_create(
                training_session=session,
                name=name,
                affiliation=affiliation
            )
            
            if created:
                created_count += 1
            else:
                skipped_count += 1
        
        return JsonResponse({
            'success': True,
            'created': created_count,
            'skipped': skipped_count,
            'message': f'{created_count}명 등록 완료 (중복 {skipped_count}명 제외)'
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def upload_participants_file(request, uuid):
    """파일(CSV, XLSX)을 통한 명단 등록"""
    from .models import ExpectedParticipant
    import csv
    import io
    
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    file_obj = request.FILES.get('file')
    
    if not file_obj:
        return JsonResponse({'success': False, 'error': '파일이 없습니다.'})
    
    file_name = file_obj.name.lower()
    participants = []
    
    try:
        if file_name.endswith('.csv'):
            # CSV 처리
            decoded_file = file_obj.read().decode('utf-8-sig').splitlines()
            reader = csv.reader(decoded_file)
            for row in reader:
                if row:
                    name = row[0].strip()
                    affiliation = row[1].strip() if len(row) > 1 else ''
                    if name: participants.append((name, affiliation))
                    
        elif file_name.endswith('.xlsx'):
            # Excel 처리
            import openpyxl
            wb = openpyxl.load_workbook(file_obj, data_only=True)
            sheet = wb.active
            for row in sheet.iter_rows(min_row=1, values_only=True):
                if row and row[0]:
                    name = str(row[0]).strip()
                    affiliation = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                    if name: participants.append((name, affiliation))
        else:
            return JsonResponse({'success': False, 'error': '참석자 명단 파일(.csv, .xlsx)만 업로드 가능합니다.'})
        
        # 데이터 저장
        created_count = 0
        skipped_count = 0
        for name, affiliation in participants:
            _, created = ExpectedParticipant.objects.get_or_create(
                training_session=session,
                name=name,
                affiliation=affiliation
            )
            if created: created_count += 1
            else: skipped_count += 1
            
        return JsonResponse({
            'success': True,
            'created': created_count,
            'skipped': skipped_count,
            'message': f'{created_count}명 등록 완료 (중복 {skipped_count}명 제외)'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'파일 처리 중 오류: {str(e)}'})


@login_required
def get_expected_participants(request, uuid):
    """예상 참석자 목록 조회 (JSON)"""
    from .models import ExpectedParticipant
    
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    participants = session.expected_participants.all()
    
    data = []
    for p in participants:
        data.append({
            'id': p.id,
            'name': p.name,
            'affiliation': p.affiliation,
            'has_signed': p.has_signed,
            'signature_id': p.matched_signature.id if p.matched_signature else None,
            'match_note': p.match_note
        })
    
    return JsonResponse({'participants': data})


@login_required
@require_POST
def delete_expected_participant(request, uuid, participant_id):
    """예상 참석자 삭제"""
    from .models import ExpectedParticipant
    
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    participant = get_object_or_404(
        ExpectedParticipant,
        id=participant_id,
        training_session=session
    )
    participant.delete()
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def match_signature(request, uuid, signature_id):
    """서명을 예상 참석자와 수동으로 연결"""
    from .models import ExpectedParticipant
    import json
    
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    signature = get_object_or_404(Signature, id=signature_id, training_session=session)
    
    try:
        data = json.loads(request.body)
        participant_id = data.get('participant_id')
        
        if not participant_id:
            return JsonResponse({'success': False, 'error': '참석자 ID가 필요합니다.'})
        
        participant = get_object_or_404(
            ExpectedParticipant,
            id=participant_id,
            training_session=session
        )
        
        # 기존 매칭 해제 (다른 서명과 연결되어 있었다면)
        if participant.matched_signature:
            return JsonResponse({
                'success': False,
                'error': f'{participant.name}은(는) 이미 다른 서명과 연결되어 있습니다.'
            })
        
        # 매칭 설정
        participant.matched_signature = signature
        participant.is_confirmed = True
        participant.save()
        
        return JsonResponse({
            'success': True,
            'message': f'{signature.participant_name} → {participant.name} 연결 완료'
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
