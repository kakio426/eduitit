import base64
import json
import os
import re
import time
from urllib.parse import parse_qs, urlencode, urlparse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.decorators import login_required
from django_ratelimit.decorators import ratelimit
from django.views.decorators.http import require_POST
from django.urls import reverse
from core.utils import ratelimit_key_for_master_only
from django.db.models import Count
from .models import ArtClass, ArtStep
from .manual_pipeline import (
    ManualPipelineError,
    build_manual_pipeline_prompt,
    parse_manual_pipeline_result,
)


def _can_manage_art_class(user, art_class):
    if not user.is_authenticated:
        return False
    return user.is_staff or art_class.created_by_id == user.id


def _extract_youtube_video_id(url):
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().replace("www.", "")

        if hostname == "youtu.be":
            path_parts = [part for part in parsed.path.split("/") if part]
            return path_parts[0] if path_parts else ""

        if hostname.endswith("youtube.com"):
            if parsed.path == "/watch":
                return (parse_qs(parsed.query).get("v") or [""])[0]
            path_parts = [part for part in parsed.path.split("/") if part]
            if path_parts and path_parts[0] in {"embed", "shorts", "live"}:
                return path_parts[1] if len(path_parts) > 1 else ""
    except Exception:
        pass

    matched = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{6,})", str(url))
    return matched.group(1) if matched else ""


def _build_external_video_loop_url(video_url):
    video_id = _extract_youtube_video_id(video_url)
    if not video_id:
        return video_url

    return (
        "https://www.youtube.com/watch?"
        + urlencode(
            {
                "v": video_id,
                "loop": "1",
                "playlist": video_id,
                "autoplay": "1",
            }
        )
    )


def _encode_launcher_payload(payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _get_launcher_download_url():
    raw_url = (os.getenv("ARTCLASS_LAUNCHER_DOWNLOAD_URL") or "").strip()
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    return ""


def setup_view(request, pk=None):
    """Setup Page - 수업 준비 및 수정 페이지"""
    art_class = None
    if pk:
        art_class = get_object_or_404(ArtClass, pk=pk)
        if not _can_manage_art_class(request.user, art_class):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            raise PermissionDenied("이 수업을 수정할 권한이 없습니다.")
         
    if request.method == 'POST':
        video_url = request.POST.get('videoUrl', '')
        interval = int(request.POST.get('stepInterval', 10))
        title = request.POST.get('title', '')
        selected_mode = (request.POST.get('playbackMode') or ArtClass.PLAYBACK_MODE_EMBED).strip()
        valid_modes = {choice[0] for choice in ArtClass.PLAYBACK_MODE_CHOICES}
        playback_mode = selected_mode if selected_mode in valid_modes else ArtClass.PLAYBACK_MODE_EMBED
        
        if art_class:
            # 기존 수업 수정
            art_class.title = title
            art_class.youtube_url = video_url
            art_class.default_interval = interval
            art_class.playback_mode = playback_mode
            art_class.save()
        else:
            # 새 수업 생성
            art_class = ArtClass.objects.create(
                title=title,
                youtube_url=video_url,
                default_interval=interval,
                playback_mode=playback_mode,
                created_by=request.user if request.user.is_authenticated else None
            )

        existing_step_image_names = {}
        if art_class.pk:
            existing_step_image_names = {
                step.pk: step.image.name
                for step in art_class.steps.all()
                if step.image
            }

        # Steps 처리
        step_count = int(request.POST.get('step_count', 0))
        step_payloads = []
        for i in range(step_count):
            description = request.POST.get(f'step_text_{i}', '')
            uploaded_image = request.FILES.get(f'step_image_{i}')
            image_value = uploaded_image

            if not image_value:
                existing_step_id_raw = (request.POST.get(f'step_existing_id_{i}') or '').strip()
                if existing_step_id_raw.isdigit():
                    existing_step_id = int(existing_step_id_raw)
                    image_value = existing_step_image_names.get(existing_step_id)

            step_payloads.append(
                {
                    'step_number': i + 1,
                    'description': description,
                    'image': image_value,
                }
            )

        if art_class.pk:
            # 기존 단계는 새 payload로 교체하되, 재업로드하지 않은 이미지는 유지한다.
            art_class.steps.all().delete()

        for payload in step_payloads:
            ArtStep.objects.create(
                art_class=art_class,
                step_number=payload['step_number'],
                description=payload['description'],
                image=payload['image'],
            )
         
        classroom_url = reverse("artclass:classroom", kwargs={"pk": art_class.pk})
        if playback_mode == ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW:
            classroom_url = f"{classroom_url}?{urlencode({'autostart_launcher': '1'})}"
        return redirect(classroom_url)
    
    # 수정 모드라면 기존 단계를 JSON으로 전달하여 JS에서 렌더링하도록 함
    initial_steps_json = "[]"
    if art_class:
        initial_steps = [
            {'id': step.pk, 'text': step.description, 'imagePreview': step.image.url if step.image else None}
            for step in art_class.steps.all()
        ]
        initial_steps_json = json.dumps(initial_steps, ensure_ascii=False)

    return render(request, 'artclass/setup.html', {
        'art_class': art_class,
        'initial_steps_json': initial_steps_json,
        'manual_prompt_template': build_manual_pipeline_prompt(art_class.youtube_url if art_class else ""),
        'launcher_download_url': _get_launcher_download_url(),
    })


def classroom_view(request, pk):
    """Classroom Page - 수업 진행 페이지"""
    art_class = get_object_or_404(ArtClass, pk=pk)
    display_mode = "dashboard" if request.GET.get("display") == "dashboard" else "classroom"
    runtime_mode = "launcher" if request.GET.get("runtime") == "launcher" else "web"
    
    # 조회수 증가
    art_class.view_count += 1
    art_class.save(update_fields=['view_count'])
    
    steps = art_class.steps.all()
    
    # JSON 형태로 전달 (JS에서 사용)
    steps_data = [
        {
            'id': step.pk,
            'step_number': step.step_number,
            'text': step.description,
            'image_url': step.image.url if step.image else None
        }
        for step in steps
    ]
    
    data = {
        'videoUrl': art_class.youtube_url,
        'stepInterval': art_class.default_interval,
        'playbackMode': art_class.playback_mode,
        'steps': steps_data
    }
    
    return render(request, 'artclass/classroom.html', {
        'art_class': art_class,
        'steps': steps,
        'data': data,
        'data_json': json.dumps(data, ensure_ascii=False),
        'display_mode': display_mode,
        'runtime_mode': runtime_mode,
        'launcher_download_url': _get_launcher_download_url(),
    })


@require_POST
def update_playback_mode_api(request, pk):
    """클래스별 유튜브 재생 모드를 저장한다."""
    art_class = get_object_or_404(ArtClass, pk=pk)
    if not request.user.is_authenticated:
        return JsonResponse({"error": "AUTH_REQUIRED", "message": "로그인이 필요합니다."}, status=401)
    if not _can_manage_art_class(request.user, art_class):
        return JsonResponse({"error": "FORBIDDEN", "message": "재생 모드를 변경할 권한이 없습니다."}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "INVALID_JSON", "message": "요청 형식이 올바르지 않습니다."}, status=400)

    mode = (payload.get("mode") or "").strip()
    valid_modes = {choice[0] for choice in ArtClass.PLAYBACK_MODE_CHOICES}
    if mode not in valid_modes:
        return JsonResponse({"error": "INVALID_MODE", "message": "지원하지 않는 재생 모드입니다."}, status=400)

    if art_class.playback_mode != mode:
        art_class.playback_mode = mode
        art_class.save(update_fields=["playback_mode"])

    return JsonResponse({"success": True, "mode": art_class.playback_mode})


@require_POST
def start_launcher_session_api(request, pk):
    """교사용 런처에서 좌/우 분할 실행에 필요한 payload를 생성한다."""
    art_class = get_object_or_404(ArtClass, pk=pk)
    if not request.user.is_authenticated:
        return JsonResponse({"error": "AUTH_REQUIRED", "message": "로그인이 필요합니다."}, status=401)
    if not _can_manage_art_class(request.user, art_class):
        return JsonResponse({"error": "FORBIDDEN", "message": "런처를 실행할 권한이 없습니다."}, status=403)

    classroom_url = request.build_absolute_uri(reverse("artclass:classroom", kwargs={"pk": art_class.pk}))
    dashboard_query = urlencode({"display": "dashboard", "runtime": "launcher"})
    dashboard_url = f"{classroom_url}?{dashboard_query}"
    youtube_url = _build_external_video_loop_url(art_class.youtube_url)

    issued_at = int(time.time())
    expires_at = issued_at + 120
    payload = {
        "version": 1,
        "classId": art_class.pk,
        "title": art_class.title or f"수업 #{art_class.pk}",
        "youtubeUrl": youtube_url,
        "dashboardUrl": dashboard_url,
        "issuedAt": issued_at,
        "expiresAt": expires_at,
    }
    encoded_payload = _encode_launcher_payload(payload)
    launcher_url = f"eduitit-launcher://launch?{urlencode({'payload': encoded_payload})}"

    if art_class.playback_mode != ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW:
        art_class.playback_mode = ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW
        art_class.save(update_fields=["playback_mode"])

    return JsonResponse(
        {
            "success": True,
            "launcherUrl": launcher_url,
            "payload": payload,
            "expiresInSec": max(0, expires_at - int(time.time())),
            "mode": art_class.playback_mode,
            "fallback": {
                "youtubeUrl": youtube_url,
                "dashboardUrl": dashboard_url,
            },
        }
    )


@ratelimit(key=ratelimit_key_for_master_only, rate='30/h', method='POST', block=True)
def parse_gemini_steps_api(request):
    """Gemini 수동 복붙 결과 파싱/검증 API."""
    if getattr(request, 'limited', False):
        return JsonResponse(
            {'error': 'LIMIT_EXCEEDED', 'message': '요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.'},
            status=429,
        )

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'INVALID_JSON', 'message': '요청 본문이 JSON 형식이 아닙니다.'}, status=400)

    raw_text = (data.get('rawText') or '').strip()
    if not raw_text:
        return JsonResponse({'error': 'EMPTY_INPUT', 'message': '붙여넣은 결과를 입력해 주세요.'}, status=400)

    try:
        parsed = parse_manual_pipeline_result(raw_text)
    except ManualPipelineError as exc:
        return JsonResponse({'error': exc.code, 'message': str(exc)}, status=400)
    except Exception:
        return JsonResponse({'error': 'INTERNAL_ERROR', 'message': '결과를 해석하는 중 오류가 발생했습니다.'}, status=500)

    prompt_template = build_manual_pipeline_prompt(data.get('videoUrl') or '')
    return JsonResponse(
        {
            'steps': parsed['steps'],
            'warnings': parsed['warnings'],
            'meta': parsed['meta'],
            'promptTemplate': prompt_template,
        }
    )


def library_view(request):
    """Shared Library - 다른 선생님들이 공유한 수업 목록"""
    query = request.GET.get('q', '')
    
    shared_classes = ArtClass.objects.select_related('created_by').annotate(
        steps_count=Count('steps')
    ).filter(is_shared=True)
    
    if query:
        shared_classes = shared_classes.filter(title__icontains=query)
    
    return render(request, 'artclass/library.html', {
        'shared_classes': shared_classes,
        'query': query,
        'launcher_download_url': _get_launcher_download_url(),
    })


@login_required
@require_POST
def delete_class_view(request, pk):
    """라이브러리에서 미술 수업 삭제"""
    art_class = get_object_or_404(ArtClass, pk=pk)

    can_delete = request.user.is_staff or art_class.created_by_id == request.user.id
    if not can_delete:
        messages.error(request, "이 수업을 삭제할 권한이 없습니다.")
        return redirect("artclass:library")

    title = art_class.title or f"수업 #{art_class.pk}"
    art_class.delete()
    messages.success(request, f'"{title}" 수업을 삭제했습니다.')
    return redirect("artclass:library")
