import base64
import io
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import timedelta

import qrcode
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils import timezone
from .models import (
    AffiliationCorrectionLog,
    ExpectedParticipant,
    Signature,
    TrainingSession,
)
from .forms import TrainingSessionForm, SignatureForm
import csv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from io import BytesIO

logger = logging.getLogger(__name__)
CALENDAR_INTEGRATION_SOURCE = "signatures_training"
SHEETBOOK_ACTION_SEED_SESSION_KEY = "sheetbook_action_seeds"
DEFAULT_AFFILIATION_SUGGESTIONS = [
    "교사",
    "교감",
    "교장",
    "담임",
    "전담",
    "보건교사",
    "사서교사",
    "영양교사",
    "상담교사",
    "행정실",
]


def _normalize_affiliation_text(value):
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    normalized = normalized.replace("—", "-").replace("–", "-")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*/\s*", "/", normalized)
    normalized = re.sub(r"\s*-\s*", "-", normalized)
    return normalized[:100]


def _build_affiliation_suggestions(session, max_items=40):
    counter = Counter()
    for raw in session.expected_participants.values_list("affiliation", flat=True):
        value = _normalize_affiliation_text(raw)
        if value:
            counter[value] += 1
    for raw in session.expected_participants.values_list("corrected_affiliation", flat=True):
        value = _normalize_affiliation_text(raw)
        if value:
            counter[value] += 1
    for raw in session.signatures.values_list("participant_affiliation", flat=True):
        value = _normalize_affiliation_text(raw)
        if value:
            counter[value] += 1
    for raw in session.signatures.values_list("corrected_affiliation", flat=True):
        value = _normalize_affiliation_text(raw)
        if value:
            counter[value] += 1

    suggestions = []
    seen = set()
    for value, _ in counter.most_common(max_items):
        if value not in seen:
            suggestions.append(value)
            seen.add(value)
    for default in DEFAULT_AFFILIATION_SUGGESTIONS:
        value = _normalize_affiliation_text(default)
        if value and value not in seen:
            suggestions.append(value)
            seen.add(value)
    for grade in range(1, 7):
        for classroom in range(1, 7):
            value = f"{grade}-{classroom}"
            if value not in seen:
                suggestions.append(value)
                seen.add(value)
            if len(suggestions) >= max_items:
                return suggestions
    return suggestions[:max_items]


def _apply_signature_affiliation_correction(signature, corrected_affiliation, reason, user):
    raw_source = str(signature.participant_affiliation or "").strip()
    normalized_source = _normalize_affiliation_text(raw_source)
    normalized_corrected = _normalize_affiliation_text(corrected_affiliation)
    reason = str(reason or "").strip()[:200]

    if not normalized_corrected:
        signature.corrected_affiliation = ""
        signature.affiliation_correction_reason = ""
        signature.affiliation_corrected_by = None
        signature.affiliation_corrected_at = None
        return
    if normalized_corrected == normalized_source and raw_source == normalized_corrected:
        signature.corrected_affiliation = ""
        signature.affiliation_correction_reason = ""
        signature.affiliation_corrected_by = None
        signature.affiliation_corrected_at = None
        return

    signature.corrected_affiliation = normalized_corrected
    signature.affiliation_correction_reason = reason
    signature.affiliation_corrected_by = user
    signature.affiliation_corrected_at = timezone.now()


def _apply_expected_participant_affiliation_correction(participant, corrected_affiliation, reason, user):
    raw_source = str(participant.affiliation or "").strip()
    normalized_source = _normalize_affiliation_text(raw_source)
    normalized_corrected = _normalize_affiliation_text(corrected_affiliation)
    reason = str(reason or "").strip()[:200]

    if not normalized_corrected:
        participant.corrected_affiliation = ""
        participant.affiliation_correction_reason = ""
        participant.affiliation_corrected_by = None
        participant.affiliation_corrected_at = None
        return
    if normalized_corrected == normalized_source and raw_source == normalized_corrected:
        participant.corrected_affiliation = ""
        participant.affiliation_correction_reason = ""
        participant.affiliation_corrected_by = None
        participant.affiliation_corrected_at = None
        return

    participant.corrected_affiliation = normalized_corrected
    participant.affiliation_correction_reason = reason
    participant.affiliation_corrected_by = user
    participant.affiliation_corrected_at = timezone.now()


def _create_affiliation_correction_log(
    *,
    session,
    target_type,
    mode,
    before_affiliation,
    after_affiliation,
    reason,
    corrected_by=None,
    signature=None,
    expected_participant=None,
):
    AffiliationCorrectionLog.objects.create(
        training_session=session,
        target_type=target_type,
        mode=mode,
        signature=signature,
        expected_participant=expected_participant,
        before_affiliation=_normalize_affiliation_text(before_affiliation),
        after_affiliation=_normalize_affiliation_text(after_affiliation),
        reason=str(reason or "").strip()[:200],
        corrected_by=corrected_by,
    )


def _build_qr_data_url(raw_text):
    if not raw_text:
        return ""

    qr_image = qrcode.make(raw_text)
    with io.BytesIO() as buffer:
        qr_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _to_aware_datetime(value):
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return timezone.localtime(value)


def _sync_calendar_event_for_training(session):
    """
    Keep signatures training schedule in classcalendar in sync.
    Fails safely if classcalendar app/model is unavailable.
    """
    try:
        from classcalendar.models import CalendarEvent
        from classcalendar.integrations import is_integration_enabled
    except Exception:
        logger.exception("[signatures] classcalendar import failed")
        return

    if not is_integration_enabled(session.created_by, CALENDAR_INTEGRATION_SOURCE):
        return

    start_at = _to_aware_datetime(session.datetime)
    end_at = start_at + timedelta(minutes=60)
    integration_key = f"signatures:{session.uuid}"
    CalendarEvent.objects.update_or_create(
        author=session.created_by,
        integration_source=CALENDAR_INTEGRATION_SOURCE,
        integration_key=integration_key,
        defaults={
            "title": f"[서명 연수] {session.title}"[:200],
            "start_time": start_at,
            "end_time": end_at,
            "is_all_day": False,
            "color": "indigo",
            "visibility": CalendarEvent.VISIBILITY_TEACHER,
            "source": CalendarEvent.SOURCE_LOCAL,
            "classroom": None,
            "is_locked": True,
        },
    )


def _delete_calendar_event_for_training(session):
    try:
        from classcalendar.models import CalendarEvent
    except Exception:
        logger.exception("[signatures] classcalendar import failed")
        return

    CalendarEvent.objects.filter(
        author=session.created_by,
        integration_source=CALENDAR_INTEGRATION_SOURCE,
        integration_key=f"signatures:{session.uuid}",
    ).delete()


def _sync_expected_participants_from_shared_roster(session):
    """Pull active members from linked handoff roster into expected participants."""
    group = session.shared_roster_group
    if not group:
        return {"created": 0, "skipped": 0, "total": 0, "group_name": ""}
    if group.owner_id != session.created_by_id:
        return {"created": 0, "skipped": 0, "total": 0, "group_name": group.name}

    created = 0
    skipped = 0
    members = group.members.filter(is_active=True).order_by("sort_order", "id")
    for member in members:
        name = (member.display_name or "").strip()
        if not name:
            skipped += 1
            continue
        affiliation = _normalize_affiliation_text(member.note)
        _, was_created = ExpectedParticipant.objects.get_or_create(
            training_session=session,
            name=name,
            affiliation=affiliation,
        )
        if was_created:
            created += 1
        else:
            skipped += 1
    return {"created": created, "skipped": skipped, "total": members.count(), "group_name": group.name}


def _peek_sheetbook_seed(request, token, *, expected_action=""):
    token = (token or "").strip()
    if not token:
        return None
    seeds = request.session.get(SHEETBOOK_ACTION_SEED_SESSION_KEY, {})
    if not isinstance(seeds, dict):
        return None
    seed = seeds.get(token)
    if not isinstance(seed, dict):
        return None
    if expected_action and seed.get("action") != expected_action:
        return None
    return seed


def _pop_sheetbook_seed(request, token, *, expected_action=""):
    token = (token or "").strip()
    if not token:
        return None
    seeds = request.session.get(SHEETBOOK_ACTION_SEED_SESSION_KEY, {})
    if not isinstance(seeds, dict):
        return None
    seed = seeds.get(token)
    if not isinstance(seed, dict):
        return None
    if expected_action and seed.get("action") != expected_action:
        return None
    seeds.pop(token, None)
    request.session[SHEETBOOK_ACTION_SEED_SESSION_KEY] = seeds
    request.session.modified = True
    return seed


def _parse_sheetbook_signature_participants(text, max_count=300):
    participants = []
    seen = set()
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        name = (parts[0] if parts else "").strip()[:100]
        affiliation = _normalize_affiliation_text(parts[1] if len(parts) >= 2 else "")
        if not name:
            continue
        dedupe_key = (name, affiliation)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        participants.append({"name": name, "affiliation": affiliation})
        if len(participants) >= max_count:
            break
    return participants


def _is_truthy_flag(value, *, default=True):
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if not normalized:
        return False
    return normalized not in {"0", "false", "off", "no", "n"}


@login_required
def session_list(request):
    """내가 만든 연수 목록"""
    sessions = TrainingSession.objects.filter(created_by=request.user)
    return render(request, 'signatures/list.html', {'sessions': sessions})


@login_required
def session_create(request):
    """연수 생성"""
    sheetbook_seed_token = (
        request.POST.get("sheetbook_seed_token")
        or request.GET.get("sb_seed")
        or ""
    ).strip()
    sheetbook_seed = _peek_sheetbook_seed(
        request,
        sheetbook_seed_token,
        expected_action="signature",
    )
    seed_data = sheetbook_seed.get("data", {}) if isinstance(sheetbook_seed, dict) else {}
    seed_data = seed_data if isinstance(seed_data, dict) else {}
    seed_participants = _parse_sheetbook_signature_participants(seed_data.get("participants_text", ""))

    prefill_initial = {}
    if seed_data:
        prefill_initial = {
            "title": str(seed_data.get("title") or "").strip()[:200],
            "print_title": str(seed_data.get("print_title") or "").strip()[:200],
            "instructor": str(seed_data.get("instructor") or "").strip()[:100],
            "location": str(seed_data.get("location") or "").strip()[:200],
            "description": str(seed_data.get("description") or "").strip()[:2000],
            "datetime": str(seed_data.get("datetime") or "").strip()[:16],
        }
        expected_count = seed_data.get("expected_count")
        if isinstance(expected_count, int) and expected_count > 0:
            prefill_initial["expected_count"] = expected_count
        elif str(expected_count).isdigit():
            prefill_initial["expected_count"] = int(str(expected_count))
        elif seed_participants:
            prefill_initial["expected_count"] = len(seed_participants)

    apply_sheetbook_participants = _is_truthy_flag(
        request.POST.get("apply_sheetbook_participants"),
        default=True,
    )

    if request.method == 'POST':
        form = TrainingSessionForm(request.POST, owner=request.user)
        if form.is_valid():
            session = form.save(commit=False)
            session.created_by = request.user
            session.save()
            roster_result = _sync_expected_participants_from_shared_roster(session)
            seed_created_count = 0
            seed_skipped_count = 0
            if seed_participants and apply_sheetbook_participants:
                for participant in seed_participants:
                    _, was_created = ExpectedParticipant.objects.get_or_create(
                        training_session=session,
                        name=participant["name"],
                        affiliation=participant["affiliation"],
                    )
                    if was_created:
                        seed_created_count += 1
                    else:
                        seed_skipped_count += 1
            if sheetbook_seed:
                _pop_sheetbook_seed(
                    request,
                    sheetbook_seed_token,
                    expected_action="signature",
                )
            _sync_calendar_event_for_training(session)
            message_parts = []
            if roster_result["total"] > 0:
                message_parts.append(
                    f"연수가 생성되었습니다. 공유 명단 '{roster_result['group_name']}'에서 {roster_result['created']}명 가져왔습니다."
                )
            else:
                message_parts.append("연수가 생성되었습니다.")
            if seed_created_count > 0:
                message_parts.append(f"교무수첩에서 참석자 후보 {seed_created_count}명을 반영했습니다.")
            elif seed_participants and apply_sheetbook_participants and seed_skipped_count > 0:
                message_parts.append("교무수첩 참석자 후보는 이미 모두 포함되어 있었어요.")
            messages.success(request, " ".join(message_parts))
            return redirect('signatures:detail', uuid=session.uuid)
    else:
        form = TrainingSessionForm(owner=request.user, initial=prefill_initial)

    participant_preview = []
    for participant in seed_participants[:5]:
        if participant["affiliation"]:
            participant_preview.append(f"{participant['name']} ({participant['affiliation']})")
        else:
            participant_preview.append(participant["name"])

    return render(
        request,
        'signatures/create.html',
        {
            'form': form,
            'sheetbook_seed_token': sheetbook_seed_token if seed_data else "",
            'sheetbook_prefill_active': bool(seed_data),
            'sheetbook_prefill_source_label': "교무수첩에서 가져온 내용을 넣어두었어요.",
            'sheetbook_prefill_participants_count': len(seed_participants),
            'sheetbook_prefill_participants_preview': participant_preview,
            'apply_sheetbook_participants': apply_sheetbook_participants,
        },
    )


@login_required
def session_detail(request, uuid):
    """연수 상세 (관리자용) - 미매칭 및 중복 감지 포함"""
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
            key = (sig.participant_name, sig.display_affiliation or '')
            sig_dict[key].append(sig)
        
        duplicates = [sigs for sigs in sig_dict.values() if len(sigs) > 1]
        share_link = request.build_absolute_uri(
            reverse("signatures:sign", kwargs={"uuid": session.uuid})
        )
        share_qr_data_url = _build_qr_data_url(share_link)
        correction_logs = session.affiliation_correction_logs.select_related(
            "corrected_by",
            "signature",
            "expected_participant",
        )[:20]

        return render(request, 'signatures/detail.html', {
            'session': session,
            'signatures': signatures,
            'expected_participants': expected,
            'unmatched_suggestions': suggestions,
            'duplicates': duplicates,
            'has_unmatched': len(suggestions) > 0,
            'has_duplicates': len(duplicates) > 0,
            'share_link': share_link,
            'share_qr_data_url': share_qr_data_url,
            'affiliation_suggestions': _build_affiliation_suggestions(session),
            'affiliation_correction_logs': correction_logs,
        })
    except Exception as e:
        traceback.print_exc()
        return HttpResponse(f"Server Error in session_detail: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status=500)



@login_required
def session_edit(request, uuid):
    """연수 수정"""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    if request.method == 'POST':
        form = TrainingSessionForm(request.POST, instance=session, owner=request.user)
        if form.is_valid():
            session = form.save()
            roster_result = _sync_expected_participants_from_shared_roster(session)
            _sync_calendar_event_for_training(session)
            if roster_result["total"] > 0 and roster_result["created"] > 0:
                messages.success(
                    request,
                    f"연수 정보가 수정되었습니다. 공유 명단에서 {roster_result['created']}명을 추가 반영했습니다.",
                )
            else:
                messages.success(request, '연수 정보가 수정되었습니다.')
            return redirect('signatures:detail', uuid=session.uuid)
    else:
        form = TrainingSessionForm(instance=session, owner=request.user)
    return render(request, 'signatures/edit.html', {'form': form, 'session': session})


@login_required
@require_POST
def sync_expected_participants_from_roster(request, uuid):
    """연결된 공유 명단을 예상 참석자 목록으로 다시 가져오기."""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    if not session.shared_roster_group:
        messages.error(request, "먼저 연수 수정에서 공유 명단을 선택해 주세요.")
        return redirect("signatures:detail", uuid=session.uuid)

    result = _sync_expected_participants_from_shared_roster(session)
    if result["total"] == 0:
        messages.warning(request, "공유 명단에 가져올 활성 멤버가 없습니다.")
    else:
        messages.success(
            request,
            f"공유 명단 '{result['group_name']}' 동기화 완료: {result['created']}명 추가, {result['skipped']}명 중복/제외",
        )
    return redirect("signatures:detail", uuid=session.uuid)


@login_required
def session_delete(request, uuid):
    """연수 삭제"""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    if request.method == 'POST':
        _delete_calendar_event_for_training(session)
        session.delete()
        messages.success(request, '연수가 삭제되었습니다.')
        return redirect('signatures:list')
    return render(request, 'signatures/delete_confirm.html', {'session': session})


def sign(request, uuid):
    """서명 페이지 (공개 - 로그인 불필요)"""
    session = get_object_or_404(TrainingSession, uuid=uuid)
    affiliation_suggestions = _build_affiliation_suggestions(session)

    if not session.is_active:
        return render(request, 'signatures/closed.html', {'session': session})

    if request.method == 'POST':
        form = SignatureForm(request.POST)
        if form.is_valid():
            signature = form.save(commit=False)
            signature.training_session = session
            signature.participant_affiliation = _normalize_affiliation_text(signature.participant_affiliation)
            signature.save()
            return render(request, 'signatures/sign_success.html', {'session': session})
    else:
        form = SignatureForm()

    return render(request, 'signatures/sign.html', {
        'session': session,
        'form': form,
        'affiliation_suggestions': affiliation_suggestions,
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
                'affiliation': p.display_affiliation,
                'original_affiliation': p.affiliation,
                'is_affiliation_corrected': bool(p.corrected_affiliation),
                'signature_data': p.matched_signature.signature_data if p.matched_signature else None,
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
                'affiliation': sig.display_affiliation,
                'original_affiliation': sig.participant_affiliation,
                'is_affiliation_corrected': bool(sig.corrected_affiliation),
                'signature_data': sig.signature_data,
            })
            signed_count += 1
            
        total_expected = session.expected_count or len(participants)
        
    else:
        # Case B: 명단이 없는 경우 (Phase 1) -> 서명 기준
        signatures = session.signatures.all().order_by('participant_name')
        for sig in signatures:
            print_items.append({
                'name': sig.participant_name,
                'affiliation': sig.display_affiliation,
                'original_affiliation': sig.participant_affiliation,
                'is_affiliation_corrected': bool(sig.corrected_affiliation),
                'signature_data': sig.signature_data,
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
            affiliation = _normalize_affiliation_text(parts[1] if len(parts) > 1 else '')
            
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
                    affiliation = _normalize_affiliation_text(row[1] if len(row) > 1 else '')
                    if name: participants.append((name, affiliation))
                    
        elif file_name.endswith('.xlsx'):
            # Excel 처리
            import openpyxl
            wb = openpyxl.load_workbook(file_obj, data_only=True)
            sheet = wb.active
            for row in sheet.iter_rows(min_row=1, values_only=True):
                if row and row[0]:
                    name = str(row[0]).strip()
                    affiliation = _normalize_affiliation_text(row[1] if len(row) > 1 and row[1] else '')
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
            'affiliation': p.display_affiliation,
            'display_affiliation': p.display_affiliation,
            'original_affiliation': p.affiliation,
            'corrected_affiliation': p.corrected_affiliation,
            'has_signed': p.has_signed,
            'signature_id': p.matched_signature.id if p.matched_signature else None,
            'match_note': p.match_note,
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


@login_required
@require_POST
def correct_signature_affiliation(request, uuid, signature_id):
    """개별 서명의 직위/학년반 정정."""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    signature = get_object_or_404(Signature, id=signature_id, training_session=session)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '요청 형식이 올바르지 않습니다.'}, status=400)

    corrected_affiliation = payload.get('corrected_affiliation', '')
    reason = payload.get('reason', '')
    before_display_affiliation = signature.display_affiliation
    before_state = (
        signature.corrected_affiliation,
        signature.affiliation_correction_reason,
        signature.affiliation_corrected_by_id,
        signature.affiliation_corrected_at,
    )
    _apply_signature_affiliation_correction(signature, corrected_affiliation, reason, request.user)
    after_state = (
        signature.corrected_affiliation,
        signature.affiliation_correction_reason,
        signature.affiliation_corrected_by_id,
        signature.affiliation_corrected_at,
    )
    if before_state != after_state:
        signature.save(
            update_fields=[
                'corrected_affiliation',
                'affiliation_correction_reason',
                'affiliation_corrected_by',
                'affiliation_corrected_at',
            ]
        )
        _create_affiliation_correction_log(
            session=session,
            target_type=AffiliationCorrectionLog.TARGET_SIGNATURE,
            mode=AffiliationCorrectionLog.MODE_SINGLE,
            before_affiliation=before_display_affiliation,
            after_affiliation=signature.display_affiliation,
            reason=reason,
            corrected_by=request.user,
            signature=signature,
        )
    return JsonResponse({
        'success': True,
        'display_affiliation': signature.display_affiliation,
        'original_affiliation': signature.participant_affiliation,
        'corrected_affiliation': signature.corrected_affiliation,
    })


@login_required
@require_POST
def correct_expected_participant_affiliation(request, uuid, participant_id):
    """개별 예상 참석자의 직위/학년반 정정."""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)
    participant = get_object_or_404(ExpectedParticipant, id=participant_id, training_session=session)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '요청 형식이 올바르지 않습니다.'}, status=400)

    corrected_affiliation = payload.get('corrected_affiliation', '')
    reason = payload.get('reason', '')
    before_display_affiliation = participant.display_affiliation
    before_state = (
        participant.corrected_affiliation,
        participant.affiliation_correction_reason,
        participant.affiliation_corrected_by_id,
        participant.affiliation_corrected_at,
    )
    _apply_expected_participant_affiliation_correction(participant, corrected_affiliation, reason, request.user)
    after_state = (
        participant.corrected_affiliation,
        participant.affiliation_correction_reason,
        participant.affiliation_corrected_by_id,
        participant.affiliation_corrected_at,
    )
    if before_state != after_state:
        participant.save(
            update_fields=[
                'corrected_affiliation',
                'affiliation_correction_reason',
                'affiliation_corrected_by',
                'affiliation_corrected_at',
            ]
        )
        _create_affiliation_correction_log(
            session=session,
            target_type=AffiliationCorrectionLog.TARGET_PARTICIPANT,
            mode=AffiliationCorrectionLog.MODE_SINGLE,
            before_affiliation=before_display_affiliation,
            after_affiliation=participant.display_affiliation,
            reason=reason,
            corrected_by=request.user,
            expected_participant=participant,
        )
    return JsonResponse({
        'success': True,
        'display_affiliation': participant.display_affiliation,
        'original_affiliation': participant.affiliation,
        'corrected_affiliation': participant.corrected_affiliation,
    })


@login_required
@require_POST
def bulk_correct_affiliation(request, uuid):
    """직위/학년반 일괄 정정."""
    session = get_object_or_404(TrainingSession, uuid=uuid, created_by=request.user)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '요청 형식이 올바르지 않습니다.'}, status=400)

    source_affiliation = _normalize_affiliation_text(payload.get('source_affiliation', ''))
    corrected_affiliation = _normalize_affiliation_text(payload.get('corrected_affiliation', ''))
    reason = str(payload.get('reason') or '').strip()[:200] or '일괄 정정'
    target = str(payload.get('target') or 'all').strip()

    if not source_affiliation:
        return JsonResponse({'success': False, 'error': '원본 직위/학년반을 입력해 주세요.'}, status=400)
    if not corrected_affiliation:
        return JsonResponse({'success': False, 'error': '정정할 직위/학년반을 입력해 주세요.'}, status=400)
    if target not in {'all', 'participants', 'signatures'}:
        return JsonResponse({'success': False, 'error': '정정 대상을 확인해 주세요.'}, status=400)

    updated_signatures = 0
    updated_participants = 0

    if target in {'all', 'signatures'}:
        signatures = session.signatures.all()
        for signature in signatures:
            if _normalize_affiliation_text(signature.display_affiliation) != source_affiliation:
                continue
            before_display_affiliation = signature.display_affiliation
            before_state = (
                signature.corrected_affiliation,
                signature.affiliation_correction_reason,
                signature.affiliation_corrected_by_id,
                signature.affiliation_corrected_at,
            )
            _apply_signature_affiliation_correction(signature, corrected_affiliation, reason, request.user)
            after_state = (
                signature.corrected_affiliation,
                signature.affiliation_correction_reason,
                signature.affiliation_corrected_by_id,
                signature.affiliation_corrected_at,
            )
            if before_state == after_state:
                continue
            signature.save(
                update_fields=[
                    'corrected_affiliation',
                    'affiliation_correction_reason',
                    'affiliation_corrected_by',
                    'affiliation_corrected_at',
                ]
            )
            _create_affiliation_correction_log(
                session=session,
                target_type=AffiliationCorrectionLog.TARGET_SIGNATURE,
                mode=AffiliationCorrectionLog.MODE_BULK,
                before_affiliation=before_display_affiliation,
                after_affiliation=signature.display_affiliation,
                reason=reason,
                corrected_by=request.user,
                signature=signature,
            )
            updated_signatures += 1

    if target in {'all', 'participants'}:
        participants = session.expected_participants.all()
        for participant in participants:
            if _normalize_affiliation_text(participant.display_affiliation) != source_affiliation:
                continue
            before_display_affiliation = participant.display_affiliation
            before_state = (
                participant.corrected_affiliation,
                participant.affiliation_correction_reason,
                participant.affiliation_corrected_by_id,
                participant.affiliation_corrected_at,
            )
            _apply_expected_participant_affiliation_correction(participant, corrected_affiliation, reason, request.user)
            after_state = (
                participant.corrected_affiliation,
                participant.affiliation_correction_reason,
                participant.affiliation_corrected_by_id,
                participant.affiliation_corrected_at,
            )
            if before_state == after_state:
                continue
            participant.save(
                update_fields=[
                    'corrected_affiliation',
                    'affiliation_correction_reason',
                    'affiliation_corrected_by',
                    'affiliation_corrected_at',
                ]
            )
            _create_affiliation_correction_log(
                session=session,
                target_type=AffiliationCorrectionLog.TARGET_PARTICIPANT,
                mode=AffiliationCorrectionLog.MODE_BULK,
                before_affiliation=before_display_affiliation,
                after_affiliation=participant.display_affiliation,
                reason=reason,
                corrected_by=request.user,
                expected_participant=participant,
            )
            updated_participants += 1

    return JsonResponse({
        'success': True,
        'updated_signatures': updated_signatures,
        'updated_participants': updated_participants,
        'updated_total': updated_signatures + updated_participants,
    })


def download_participant_template(request, format='csv'):
    """예상 참석자 명단 양식 다운로드 (CSV 또는 Excel)"""

    if format == 'csv':
        # CSV 파일 생성
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="참석자명단_양식.csv"'

        writer = csv.writer(response)
        writer.writerow(['이름', '소속/학년반'])
        writer.writerow(['홍길동', '1-1'])
        writer.writerow(['김철수', '1-2'])
        writer.writerow(['박영희', '교사'])
        writer.writerow(['이순신', '2-1'])
        writer.writerow(['최영', '3-1'])

        return response

    elif format == 'excel':
        # Excel 파일 생성
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "참석자 명단"

        # 헤더 스타일
        header_fill = PatternFill(start_color="7B68EE", end_color="7B68EE", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=12)
        header_alignment = Alignment(horizontal="center", vertical="center")

        # 헤더 작성
        ws['A1'] = '이름'
        ws['B1'] = '소속/학년반'

        for cell in ['A1', 'B1']:
            ws[cell].fill = header_fill
            ws[cell].font = header_font
            ws[cell].alignment = header_alignment

        # 예시 데이터
        example_data = [
            ['홍길동', '1-1'],
            ['김철수', '1-2'],
            ['박영희', '교사'],
            ['이순신', '2-1'],
            ['최영', '3-1'],
        ]

        for idx, row in enumerate(example_data, start=2):
            ws[f'A{idx}'] = row[0]
            ws[f'B{idx}'] = row[1]
            # 텍스트 형식으로 명시 (날짜 자동 변환 방지)
            ws[f'A{idx}'].number_format = '@'
            ws[f'B{idx}'].number_format = '@'

        # 열 너비 조정
        ws.column_dimensions['A'].width = 15
        ws.column_dimensions['B'].width = 20

        # 안내 시트 추가
        ws_guide = wb.create_sheet("사용 안내")
        ws_guide['A1'] = "📋 참석자 명단 작성 안내"
        ws_guide['A1'].font = Font(bold=True, size=14, color="7B68EE")

        ws_guide['A3'] = "1. 첫 번째 열에 참석자 이름을 입력하세요."
        ws_guide['A4'] = "2. 두 번째 열에 소속이나 학년반을 입력하세요."
        ws_guide['A5'] = "3. 헤더(첫 번째 행)는 삭제하지 마세요."
        ws_guide['A6'] = "4. 예시 데이터는 삭제하고 실제 데이터를 입력하세요."
        ws_guide['A7'] = "5. 완성 후 파일을 저장하고 업로드하세요."

        ws_guide.column_dimensions['A'].width = 60

        # 파일 저장
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="참석자명단_양식.xlsx"'

        return response

    else:
        return HttpResponse("Invalid format", status=400)
