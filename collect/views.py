from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from asgiref.sync import sync_to_async
import json
import csv
import qrcode
from io import BytesIO
import base64
import logging
import requests

from .models import CollectionRequest, Submission
from .forms import CollectionRequestForm
from products.models import Product

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 30 * 1024 * 1024  # 30MB
DEFAULT_DEADLINE_EXTENSION_DAYS = 1
DEFAULT_RETENTION_EXTENSION_DAYS = 7
ALLOWED_EXTENSION_DAYS = {1, 3, 7, 14, 30}
_STREAM_END = object()


def _next_or_end(iterator):
    return next(iterator, _STREAM_END)


async def _async_wrap_sync_iterable(iterable):
    """Adapt a sync iterable to an async iterator for ASGI StreamingHttpResponse."""
    iterator = iter(iterable)
    while True:
        chunk = await sync_to_async(_next_or_end, thread_sensitive=True)(iterator)
        if chunk is _STREAM_END:
            break
        yield chunk


def _remote_file_chunks(file_url, chunk_size=8192):
    with requests.get(file_url, stream=True, timeout=(5, 60)) as resp:
        resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if chunk:
                yield chunk


def _parse_extension_days(raw_days, fallback):
    try:
        days = int(raw_days)
    except (TypeError, ValueError):
        return fallback
    if days not in ALLOWED_EXTENSION_DAYS:
        return fallback
    return days


def _get_submit_context(
    collection_req,
    submission=None,
    is_edit=False,
    error=None,
    form_data=None,
    initial_submission_type=None,
    choice_values=None,
    choice_other_text=None,
):
    allowed_types = collection_req.allowed_submission_types
    initial_type = initial_submission_type
    if is_edit and submission:
        initial_type = submission.submission_type
    if not (is_edit and submission) and initial_type not in allowed_types:
        initial_type = allowed_types[0] if allowed_types else ""

    resolved_choice_values = choice_values
    resolved_choice_other_text = choice_other_text

    if resolved_choice_values is None and submission and submission.submission_type == "choice":
        stored = submission.choice_answers if isinstance(submission.choice_answers, list) else []
        resolved_choice_values = [str(value).strip() for value in stored if str(value).strip()]
        if submission.choice_other_text.strip():
            resolved_choice_values.append("__other__")
    if resolved_choice_values is None:
        resolved_choice_values = []

    if resolved_choice_other_text is None and submission and submission.submission_type == "choice":
        resolved_choice_other_text = submission.choice_other_text
    if resolved_choice_other_text is None:
        resolved_choice_other_text = ""

    return {
        "req": collection_req,
        "submission": submission,
        "is_edit": is_edit,
        "error": error,
        "form_data": form_data,
        "allowed_submission_types": allowed_types,
        "initial_submission_type": initial_type,
        "choice_values": resolved_choice_values,
        "choice_other_text": resolved_choice_other_text,
    }


def _render_submit_error(
    request,
    collection_req,
    error_message,
    submission_type="",
    is_edit=False,
    submission=None,
    form_data=None,
):
    posted = form_data or request.POST
    choice_values = posted.getlist("choice_answers") if posted else []
    choice_other_text = posted.get("choice_other_text", "").strip() if posted else ""
    return render(
        request,
        "collect/submit.html",
        _get_submit_context(
            collection_req,
            submission=submission,
            is_edit=is_edit,
            error=error_message,
            form_data=posted,
            initial_submission_type=submission_type,
            choice_values=choice_values,
            choice_other_text=choice_other_text,
        ),
    )


def _extract_choice_submission_data(collection_req, post_data):
    options = collection_req.normalized_choice_options
    if not options:
        return None, None, "선택형 보기가 아직 설정되지 않았습니다. 요청 생성자에게 문의해주세요."

    selected_raw = [value.strip() for value in post_data.getlist("choice_answers") if value.strip()]
    selected_options = []
    seen = set()
    for value in selected_raw:
        if value in options and value not in seen:
            selected_options.append(value)
            seen.add(value)

    other_text = post_data.get("choice_other_text", "").strip()
    use_other = collection_req.choice_allow_other and ("__other__" in selected_raw or bool(other_text))

    if collection_req.choice_allow_other:
        if use_other and not other_text:
            return None, None, "기타 내용을 입력해주세요."
        if not use_other:
            other_text = ""
    else:
        other_text = ""

    selected_count = len(selected_options) + (1 if other_text else 0)
    if collection_req.choice_mode == "single":
        if selected_count != 1:
            return None, None, "선택형은 한 가지 보기만 선택해주세요."
    else:
        min_count = max(collection_req.choice_min_selections or 1, 1)
        max_count = collection_req.choice_max_selections
        if selected_count < min_count:
            return None, None, f"최소 {min_count}개 이상 선택해주세요."
        if max_count is not None and selected_count > max_count:
            return None, None, f"최대 {max_count}개까지 선택할 수 있습니다."

    return selected_options, other_text, None


def get_collect_service():
    """서비스 정보 로드"""
    return Product.objects.filter(title__icontains="간편 수합").first()


def generate_qr(url):
    """QR 코드 생성 (Base64 반환)"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode()


# ================================
# 공개 랜딩 페이지
# ================================

def landing(request):
    """서비스 소개 + 입장코드 입력"""
    service = get_collect_service()
    
    # 기능 중복 제거 (임시 조치: DB에 중복데이터가 있어도 화면에는 1개만 표시)
    features = []
    if service:
        seen_titles = set()
        for feature in service.features.all():
            if feature.title not in seen_titles:
                features.append(feature)
                seen_titles.add(feature.title)

    return render(request, 'collect/landing.html', {
        'service': service,
        'features': features,
    })


# ================================
# 교사용 (로그인 필수)
# ================================

@login_required
def dashboard(request):
    """내 수합 목록 + 생성 폼"""
    service = get_collect_service()
    requests_list = CollectionRequest.objects.filter(
        creator=request.user
    ).annotate(
        num_submissions=Count('submissions')
    ).order_by('-created_at')

    form = CollectionRequestForm()

    return render(request, 'collect/dashboard.html', {
        'service': service,
        'requests_list': requests_list,
        'form': form,
    })


@login_required
@require_POST
def request_create(request):
    """새 수합 요청 생성"""
    form = CollectionRequestForm(request.POST, request.FILES)
    if form.is_valid():
        collection_req = form.save(commit=False)
        collection_req.creator = request.user
        
        if request.FILES.get('template_file'):
            collection_req.template_file_name = request.FILES['template_file'].name
            
        collection_req.save()
        return redirect('collect:request_detail', request_id=str(collection_req.id))

    # 폼 오류 시 대시보드로 복귀
    service = get_collect_service()
    requests_list = CollectionRequest.objects.filter(
        creator=request.user
    ).annotate(
        num_submissions=Count('submissions')
    ).order_by('-created_at')

    return render(request, 'collect/dashboard.html', {
        'service': service,
        'requests_list': requests_list,
        'form': form,
    })


@login_required
def request_detail(request, request_id):
    """QR/코드 + 실시간 제출 현황 + 다운로드"""
    collection_req = get_object_or_404(CollectionRequest, id=request_id, creator=request.user)
    submissions = collection_req.submissions.all()

    # QR 코드 생성 (단축 링크 사용)
    short_url = request.build_absolute_uri(reverse('collect:short_link', args=[collection_req.access_code]))
    qr_code_base64 = generate_qr(short_url)

    # 제출 유형별 통계
    type_stats = submissions.values('submission_type').annotate(count=Count('id'))

    # 제출 대상자 현황
    expected = collection_req.expected_submitters_list
    submitted_names = set(submissions.values_list('contributor_name', flat=True))
    not_submitted = [name for name in expected if name not in submitted_names]

    # 파일 데이터 JSON 구성을 위한 리스트
    files_data = []
    for sub in submissions:
        if sub.submission_type == 'file' and sub.file:
            aff = f"[{sub.contributor_affiliation}]_" if sub.contributor_affiliation else ""
            descriptive_name = f"{aff}{sub.contributor_name}_{sub.original_filename}"
            files_data.append({
                'url': reverse('collect:submission_download', args=[sub.id]),
                'name': descriptive_name,
                'contributor': sub.contributor_name
            })

    return render(request, 'collect/request_detail.html', {
        'req': collection_req,
        'submissions': submissions,
        'qr_code_base64': qr_code_base64,
        'total_count': submissions.count(),
        'type_stats': {s['submission_type']: s['count'] for s in type_stats},
        'expected_submitters': expected,
        'not_submitted': not_submitted,
        'files_data': files_data,
    })


@login_required
def submissions_partial(request, request_id):
    """HTMX 폴링용 - 제출물 목록 부분 렌더링"""
    collection_req = get_object_or_404(CollectionRequest, id=request_id, creator=request.user)
    submissions = collection_req.submissions.all()
    expected = collection_req.expected_submitters_list
    submitted_names = set(submissions.values_list('contributor_name', flat=True))
    not_submitted = [name for name in expected if name not in submitted_names]
    return render(request, 'collect/partials/submissions_list.html', {
        'submissions': submissions,
        'total_count': submissions.count(),
        'expected_submitters': expected,
        'not_submitted': not_submitted,
    })


@login_required
@require_POST
def request_toggle(request, request_id):
    """마감/재개 토글"""
    collection_req = get_object_or_404(CollectionRequest, id=request_id, creator=request.user)
    if collection_req.status == 'active':
        collection_req.status = 'closed'
        collection_req.closed_at = timezone.now()
    else:
        collection_req.status = 'active'
        collection_req.closed_at = None
    collection_req.save(update_fields=["status", "closed_at", "updated_at"])
    return redirect('collect:request_detail', request_id=collection_req.id)


@login_required
@require_POST
def request_extend_deadline(request, request_id):
    """마감 기한 연장"""
    collection_req = get_object_or_404(CollectionRequest, id=request_id, creator=request.user)
    days = _parse_extension_days(request.POST.get("days"), DEFAULT_DEADLINE_EXTENSION_DAYS)
    collection_req.extend_deadline(days)
    messages.success(request, f"마감 기한을 {days}일 연장했습니다.")
    return redirect('collect:request_detail', request_id=collection_req.id)


@login_required
@require_POST
def request_extend_retention(request, request_id):
    """자동 정리 유예 기한 연장"""
    collection_req = get_object_or_404(CollectionRequest, id=request_id, creator=request.user)
    days = _parse_extension_days(request.POST.get("days"), DEFAULT_RETENTION_EXTENSION_DAYS)
    collection_req.extend_retention(days)
    messages.success(request, f"보관 기간을 {days}일 연장했습니다.")
    return redirect('collect:request_detail', request_id=collection_req.id)


@login_required
@require_POST
def request_delete(request, request_id):
    """수합 요청 삭제"""
    collection_req = get_object_or_404(CollectionRequest, id=request_id, creator=request.user)
    collection_req.delete()
    logger.info(f"[Collect] Request Deleted: {request_id} by {request.user.username}")
    return redirect('collect:dashboard')


@login_required
def export_csv(request, request_id):
    """제출 목록 CSV 내보내기"""
    collection_req = get_object_or_404(CollectionRequest, id=request_id, creator=request.user)
    submissions = collection_req.submissions.all().order_by('submitted_at')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{collection_req.title}_submissions.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow(['번호', '이름', '소속', '유형', '파일명/링크/내용', '제출시간'])

    for idx, sub in enumerate(submissions, 1):
        if sub.submission_type == 'file':
            content = sub.original_filename
        elif sub.submission_type == 'link':
            content = sub.link_url
        elif sub.submission_type == 'choice':
            content = sub.choice_summary
        else:
            content = sub.text_content[:100]

        writer.writerow([
            idx,
            sub.contributor_name,
            sub.contributor_affiliation,
            sub.get_submission_type_display(),
            content,
            sub.submitted_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response


# ================================
# 제출자용 (비로그인)
# ================================

def short_link(request, code):
    """단축 링크로 바로 제출 페이지 이동"""
    collection_req = get_object_or_404(CollectionRequest, access_code=code)
    
    if collection_req.status != 'active':
        return render(request, 'collect/request_closed.html', {'req': collection_req})
        
    return redirect('collect:submit', request_id=collection_req.id)


def join(request):
    """입장코드로 수합 참여"""
    code = request.GET.get('code', '').strip()
    if not code:
        code = request.POST.get('code', '').strip()

    if code:
        collection_req = CollectionRequest.objects.filter(access_code=code, status='active').first()
        if collection_req:
            return redirect('collect:submit', request_id=collection_req.id)
        # 마감된 수합인지 확인
        closed_req = CollectionRequest.objects.filter(access_code=code).first()
        if closed_req:
            return render(request, 'collect/request_closed.html', {'req': closed_req})
        return render(request, 'collect/landing.html', {
            'service': get_collect_service(),
            'error': '유효하지 않은 입장코드입니다.',
        })

    return redirect('collect:landing')


def submit(request, request_id):
    """제출 페이지"""
    collection_req = get_object_or_404(CollectionRequest, id=request_id)

    if collection_req.status != 'active':
        return render(request, 'collect/request_closed.html', {'req': collection_req})

    # 마감일 초과 확인
    if collection_req.is_deadline_passed:
        collection_req.status = 'closed'
        if not collection_req.closed_at:
            collection_req.closed_at = timezone.now()
        collection_req.save(update_fields=["status", "closed_at", "updated_at"])
        return render(request, 'collect/request_closed.html', {'req': collection_req})

    # 최대 제출 수 확인
    if collection_req.submission_count >= collection_req.max_submissions:
        return render(request, 'collect/request_closed.html', {
            'req': collection_req,
            'reason': '최대 제출 건수에 도달했습니다.',
        })

    if not collection_req.allowed_submission_types:
        return render(request, 'collect/request_closed.html', {
            'req': collection_req,
            'reason': '이 요청은 현재 제출 가능한 유형이 없습니다.',
        })

    return render(request, 'collect/submit.html', _get_submit_context(collection_req))


@require_POST
def submit_process(request, request_id):
    """제출 처리"""
    collection_req = get_object_or_404(CollectionRequest, id=request_id)

    if collection_req.status != 'active':
        return render(request, 'collect/request_closed.html', {'req': collection_req})

    allowed_types = collection_req.allowed_submission_types
    if not allowed_types:
        return render(request, 'collect/request_closed.html', {
            'req': collection_req,
            'reason': '이 요청은 현재 제출 가능한 유형이 없습니다.',
        })

    # 이름: 직접 입력 > 셀렉트 > 일반 입력
    contributor_name = request.POST.get('contributor_name_custom', '').strip()
    if not contributor_name:
        selected = request.POST.get('contributor_name_select', '').strip()
        if selected and selected != '__custom__':
            contributor_name = selected
    if not contributor_name:
        contributor_name = request.POST.get('contributor_name', '').strip()
    contributor_affiliation = request.POST.get('contributor_affiliation', '').strip()
    submission_type = request.POST.get('submission_type', '')

    if not contributor_name:
        return _render_submit_error(
            request,
            collection_req,
            '이름을 입력해주세요.',
            submission_type=submission_type,
        )

    valid_types = {choice[0] for choice in Submission.TYPE_CHOICES}
    if submission_type not in valid_types:
        return _render_submit_error(
            request,
            collection_req,
            '제출 유형을 선택해주세요.',
            submission_type=submission_type,
        )
    if submission_type not in allowed_types:
        return _render_submit_error(
            request,
            collection_req,
            '이 요청에서는 해당 제출 유형을 사용할 수 없습니다.',
            submission_type=submission_type,
        )

    submission = Submission(
        collection_request=collection_req,
        contributor_name=contributor_name,
        contributor_affiliation=contributor_affiliation,
        submission_type=submission_type,
    )

    if submission_type == 'file':
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return _render_submit_error(
                request,
                collection_req,
                '파일을 선택해주세요.',
                submission_type=submission_type,
            )
        max_size = collection_req.max_file_size_mb * 1024 * 1024
        if uploaded_file.size > max_size:
            return _render_submit_error(
                request,
                collection_req,
                f'파일 크기가 {collection_req.max_file_size_mb}MB를 초과합니다. 링크로 제출해주세요.',
                submission_type=submission_type,
            )
        submission.file = uploaded_file
        submission.original_filename = uploaded_file.name
        submission.file_size = uploaded_file.size
        
        # 파일 설명 저장
        submission.text_content = request.POST.get('file_description', '').strip()

    elif submission_type == 'link':
        link_url = request.POST.get('link_url', '').strip()
        link_description = request.POST.get('link_description', '').strip()
        if not link_url:
            return _render_submit_error(
                request,
                collection_req,
                '링크를 입력해주세요.',
                submission_type=submission_type,
            )
        submission.link_url = link_url
        submission.link_description = link_description

    elif submission_type == 'text':
        text_content = request.POST.get('text_content', '').strip()
        if not text_content:
            return _render_submit_error(
                request,
                collection_req,
                '내용을 입력해주세요.',
                submission_type=submission_type,
            )
        submission.text_content = text_content

    elif submission_type == 'choice':
        choice_answers, choice_other_text, choice_error = _extract_choice_submission_data(collection_req, request.POST)
        if choice_error:
            return _render_submit_error(
                request,
                collection_req,
                choice_error,
                submission_type=submission_type,
            )
        submission.choice_answers = choice_answers
        submission.choice_other_text = choice_other_text

    submission.save()
    logger.info(f"[Collect] Submission saved: {submission.id}")

    # UUID 기반 매니지먼트 페이지로 이동

    return redirect('collect:submission_manage', management_id=submission.management_id)


# ================================
# 제출물 관리 및 다운로드
# ================================

def submission_manage(request, management_id):
    """제출물 관리 페이지 (수정/삭제 안내)"""
    submission = get_object_or_404(Submission, management_id=management_id)
    # UUID 자체가 보안 코드 역할을 하므로 세션 체크 없이 접근 허용
    can_manage = True
    
    return render(request, 'collect/submission_manage.html', {
        'submission': submission,
        'req': submission.collection_request,
        'can_manage': can_manage
    })


def submission_edit(request, management_id):
    """제출물 수정 페이지"""
    submission = get_object_or_404(Submission, management_id=management_id)
    
    # UUID 기반으로 동작하므로 세션 체크 생략 (링크를 가진 사람이 권한자)
        
    if request.method == 'POST':
        contributor_name = request.POST.get('contributor_name_custom', '').strip()
        if not contributor_name:
            selected = request.POST.get('contributor_name_select', '').strip()
            if selected and selected != '__custom__':
                contributor_name = selected
        if not contributor_name:
            contributor_name = request.POST.get('contributor_name', '').strip()
        contributor_affiliation = request.POST.get('contributor_affiliation', '').strip()

        if not contributor_name:
            return _render_submit_error(
                request,
                submission.collection_request,
                "이름을 입력해주세요.",
                submission_type=submission.submission_type,
                is_edit=True,
                submission=submission,
            )

        submission.contributor_name = contributor_name
        submission.contributor_affiliation = contributor_affiliation

        if submission.submission_type == 'file':
            uploaded_file = request.FILES.get('file')
            if uploaded_file:
                max_size = submission.collection_request.max_file_size_mb * 1024 * 1024
                if uploaded_file.size > max_size:
                    return _render_submit_error(
                        request,
                        submission.collection_request,
                        f'파일 크기가 {submission.collection_request.max_file_size_mb}MB를 초과합니다. 링크로 제출해주세요.',
                        submission_type=submission.submission_type,
                        is_edit=True,
                        submission=submission,
                    )
                submission.file = uploaded_file
                submission.original_filename = uploaded_file.name
                submission.file_size = uploaded_file.size

            submission.text_content = request.POST.get('file_description', submission.text_content).strip()

        elif submission.submission_type == 'link':
            link_url = request.POST.get('link_url', '').strip()
            if not link_url:
                return _render_submit_error(
                    request,
                    submission.collection_request,
                    "링크를 입력해주세요.",
                    submission_type=submission.submission_type,
                    is_edit=True,
                    submission=submission,
                )
            submission.link_url = link_url
            submission.link_description = request.POST.get('link_description', '').strip()

        elif submission.submission_type == 'text':
            text_content = request.POST.get('text_content', '').strip()
            if not text_content:
                return _render_submit_error(
                    request,
                    submission.collection_request,
                    "내용을 입력해주세요.",
                    submission_type=submission.submission_type,
                    is_edit=True,
                    submission=submission,
                )
            submission.text_content = text_content

        elif submission.submission_type == 'choice':
            choice_answers, choice_other_text, choice_error = _extract_choice_submission_data(
                submission.collection_request,
                request.POST,
            )
            if choice_error:
                return _render_submit_error(
                    request,
                    submission.collection_request,
                    choice_error,
                    submission_type=submission.submission_type,
                    is_edit=True,
                    submission=submission,
                )
            submission.choice_answers = choice_answers
            submission.choice_other_text = choice_other_text

        submission.save()
        messages.success(request, '제출 정보가 수정되었습니다.')
        return redirect('collect:submission_manage', management_id=management_id)

    return render(
        request,
        'collect/submit.html',
        _get_submit_context(submission.collection_request, submission=submission, is_edit=True),
    )


@require_POST
def submission_delete(request, management_id):
    """제출물 삭제"""
    submission = get_object_or_404(Submission, management_id=management_id)
    
    # UUID 기반 권한 확인
        
    req_id = submission.collection_request.id
    submission.delete()
    messages.success(request, '제출물이 삭제되었습니다.')
    return redirect('collect:submit', request_id=req_id)


def submission_download(request, submission_id):
    """파일명 변경하여 파일 다운로드"""
    submission = get_object_or_404(Submission, id=submission_id)
    
    if not request.user.is_authenticated or submission.collection_request.creator != request.user:
        return HttpResponse("권한이 없습니다.", status=403)
        
    if not submission.file:
        return HttpResponse("파일이 없습니다.", status=404)

    aff = f"[{submission.contributor_affiliation}]_" if submission.contributor_affiliation else ""
    safe_name = f"{aff}{submission.contributor_name}_{submission.original_filename}"
    import urllib.parse
    encoded_filename = urllib.parse.quote(safe_name)

    from django.http import StreamingHttpResponse

    file_url = submission.file.url
    
    if file_url.startswith('http'):
        response = StreamingHttpResponse(_async_wrap_sync_iterable(_remote_file_chunks(file_url)))
    else:
        response = StreamingHttpResponse(_async_wrap_sync_iterable(submission.file.chunks()))

    response['Content-Type'] = 'application/octet-stream'
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
    
    return response


def template_download(request, request_id):
    """양식 파일 다운로드"""
    collection_req = get_object_or_404(CollectionRequest, id=request_id)
    if not collection_req.template_file:
        return HttpResponse("양식 파일이 없습니다.", status=404)

    return redirect(collection_req.template_file.url)
