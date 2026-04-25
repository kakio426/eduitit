import base64
import io
import json
import logging
import time
import uuid
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F as models_F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from PIL import Image

from .models import GuideSession, GuideStep
from .services import image_annotator

logger = logging.getLogger(__name__)


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def _require_superuser(request):
    """superuser가 아니면 JsonResponse(403)을 반환한다. None이면 통과."""
    if not (request.user.is_authenticated and request.user.is_superuser):
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    return None


def _auto_description(metadata: dict) -> str:
    """element_metadata로 자동 설명 생성."""
    tag = (metadata.get('tag') or '').lower()
    text = (metadata.get('text') or '').strip()[:60]

    if text:
        return f'"{text}" 버튼을 클릭하세요'
    if tag == 'a':
        return '링크를 클릭하세요'
    if tag in ('input', 'textarea'):
        return '입력란을 클릭하세요'
    if tag == 'select':
        return '드롭다운을 클릭하세요'
    return '해당 영역을 클릭하세요'


def _build_share_url(request, session):
    """공유 토큰이 있을 때만 절대 URL 반환."""
    if not session.share_token:
        return None
    return request.build_absolute_uri(
        reverse('guide_recorder:share', kwargs={'token': session.share_token})
    )


# ── 페이지 뷰 ─────────────────────────────────────────────────────────────────

@login_required
def session_list_view(request):
    qs = GuideSession.objects.filter(created_by=request.user)
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'guide_recorder/session_list.html', {
        'page_title': '내 가이드',
        'sessions': page,
    })


@login_required
def session_detail_view(request, pk):
    # ownership을 단일 쿼리로 검증 — 세션 존재 여부 노출 방지
    session = get_object_or_404(GuideSession, pk=pk, created_by=request.user)
    steps = session.steps.all()
    return render(request, 'guide_recorder/session_detail.html', {
        'page_title': session.title,
        'session': session,
        'steps': steps,
        'can_edit': True,
        'share_url': _build_share_url(request, session),
    })


def share_view(request, token):
    """비공개 링크 뷰어 — 로그인 불필요."""
    session = get_object_or_404(GuideSession, share_token=token, is_published=True)
    steps = session.steps.all()
    return render(request, 'guide_recorder/session_detail.html', {
        'page_title': session.title,
        'session': session,
        'steps': steps,
        'can_edit': False,
        'is_public_view': True,
    })


@login_required
@require_POST
def delete_session_view(request, pk):
    session = get_object_or_404(GuideSession, pk=pk, created_by=request.user)
    session.delete()
    if request.headers.get('HX-Request'):
        return JsonResponse({'ok': True})
    return redirect('guide_recorder:session_list')


@login_required
@require_POST
def publish_session_view(request, pk):
    session = get_object_or_404(GuideSession, pk=pk, created_by=request.user)
    session.is_published = not session.is_published
    if session.is_published and not session.share_token:
        session.share_token = uuid.uuid4().hex
    session.save(update_fields=['is_published', 'share_token'])
    share_url = _build_share_url(request, session) if session.is_published else None
    return JsonResponse({'ok': True, 'is_published': session.is_published, 'share_url': share_url})


# ── API 뷰 ────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def api_start_session(request):
    err = _require_superuser(request)
    if err:
        return err
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        body = {}

    title = (body.get('title') or '').strip()
    if not title:
        title = datetime.now().strftime('%Y-%m-%d %H:%M 가이드')

    session = GuideSession.objects.create(
        title=title,
        created_by=request.user,
    )
    return JsonResponse({'ok': True, 'session_id': session.pk})


@login_required
@require_POST
def api_add_step(request, pk):
    err = _require_superuser(request)
    if err:
        return err

    # 페이로드 크기 제한 (10MB — settings에서 DATA_UPLOAD_MAX_MEMORY_SIZE로 1차 차단)
    if int(request.META.get('CONTENT_LENGTH', 0)) > 10 * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'payload_too_large'}, status=413)

    session = get_object_or_404(GuideSession, pk=pk, created_by=request.user)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)

    screenshot_b64 = body.get('screenshot', '')
    canvas_width = int(body.get('canvas_width') or 1)
    canvas_height = int(body.get('canvas_height') or 1)
    click_x_px = float(body.get('click_x') or 0)
    click_y_px = float(body.get('click_y') or 0)
    metadata = body.get('element_metadata') or {}

    if not screenshot_b64:
        return JsonResponse({'ok': False, 'error': 'missing_screenshot'}, status=400)

    # Base64 → PIL Image
    try:
        raw = screenshot_b64.split(',', 1)[-1]
        img_bytes = base64.b64decode(raw)
        pil_img = Image.open(io.BytesIO(img_bytes))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'invalid_image'}, status=400)

    # 정규화 좌표 계산
    norm_x = click_x_px / canvas_width if canvas_width else 0.5
    norm_y = click_y_px / canvas_height if canvas_height else 0.5
    norm_x = max(0.0, min(1.0, norm_x))
    norm_y = max(0.0, min(1.0, norm_y))

    # 어노테이션 + JPEG 변환 — 트랜잭션 바깥에서 수행 (Cloudinary 업로드 포함)
    try:
        annotated = image_annotator.annotate(pil_img, norm_x, norm_y, metadata)
        jpeg_bytes = image_annotator.to_jpeg_bytes(annotated)
    except Exception:
        logger.exception('[guide_recorder] annotate 실패 session=%s', pk)
        return JsonResponse({'ok': False, 'error': '이미지 처리에 실패했습니다. 다시 시도해 주세요.'}, status=500)

    description = _auto_description(metadata)
    filename = f'step_tmp_{int(time.time())}.jpg'
    django_file = ContentFile(jpeg_bytes, name=filename)

    # ① 파일을 먼저 스토리지에 업로드 (트랜잭션 바깥)
    step_placeholder = GuideStep(session=session, order=0)
    step_placeholder.screenshot.save(filename, django_file, save=False)
    saved_name = step_placeholder.screenshot.name  # 업로드된 경로 확보

    # ② order 할당 + DB 저장만 트랜잭션 안에서
    with transaction.atomic():
        locked = GuideSession.objects.select_for_update().get(pk=session.pk)
        order = locked.step_count + 1
        step = GuideStep.objects.create(
            session=locked,
            order=order,
            description=description,
            click_x=norm_x,
            click_y=norm_y,
            element_metadata=metadata,
            screenshot=saved_name,
        )
        locked.step_count = order
        locked.save(update_fields=['step_count'])

    return JsonResponse({'ok': True, 'step_id': step.pk, 'order': order})


@login_required
@require_POST
def api_finish_session(request, pk):
    err = _require_superuser(request)
    if err:
        return err
    session = get_object_or_404(GuideSession, pk=pk, created_by=request.user)
    redirect_url = reverse('guide_recorder:session_detail', kwargs={'pk': session.pk})
    return JsonResponse({'ok': True, 'redirect_url': redirect_url})


@login_required
@require_POST
def api_update_description(request, pk):
    step = get_object_or_404(GuideStep, pk=pk)
    if step.session.created_by != request.user:
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'invalid_json'}, status=400)
    desc = (body.get('description') or '').strip()[:500]
    step.description = desc
    step.save(update_fields=['description'])
    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_delete_step(request, pk):
    step = get_object_or_404(GuideStep, pk=pk)
    session = step.session
    if session.created_by != request.user:
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)
    deleted_order = step.order
    with transaction.atomic():
        step.delete()
        # order 재정렬: 삭제된 order 이후 스텝들을 1씩 당김
        session.steps.filter(order__gt=deleted_order).update(
            order=models_F('order') - 1
        )
        session.step_count = session.steps.count()
        session.save(update_fields=['step_count'])
    return JsonResponse({'ok': True})
