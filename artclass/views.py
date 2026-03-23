import base64
import json
import os
import re
import time
from urllib.request import Request, urlopen
from urllib.parse import parse_qs, urlencode, urlparse
from PIL import Image, UnidentifiedImageError
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
from django.db.models import Count, Q
from .models import ArtClass, ArtStep
from .classification import apply_auto_metadata, collect_popular_tags
from .manual_pipeline import (
    ManualPipelineError,
    build_manual_pipeline_prompt,
    parse_manual_pipeline_result,
)


def _can_manage_art_class(user, art_class):
    if not user.is_authenticated:
        return False
    return user.is_staff or art_class.created_by_id == user.id


def _resolve_creator_display_name(user):
    if not user:
        return "익명의 선생님"

    nickname = ""
    try:
        profile = user.userprofile
        nickname = (profile.nickname or "").strip()
    except Exception:
        nickname = ""

    if nickname:
        return nickname

    username = (getattr(user, "username", "") or "").strip()
    if username and not re.match(r"^user\d+$", username, flags=re.IGNORECASE):
        return username
    return "익명의 선생님"


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


def _fetch_youtube_title(video_url):
    video_id = _extract_youtube_video_id(video_url)
    if not video_id:
        return ""

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    oembed_url = "https://www.youtube.com/oembed?" + urlencode(
        {"url": canonical_url, "format": "json"}
    )
    request = Request(
        oembed_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; Eduitit ArtClass Bot/1.0)"},
    )

    try:
        with urlopen(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return ""

    title = str(payload.get("title") or "").strip()
    if not title:
        return ""
    return title[:200]


def _encode_launcher_payload(payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _get_launcher_download_url():
    raw_url = (os.getenv("ARTCLASS_LAUNCHER_DOWNLOAD_URL") or "").strip()
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    return ""


VIDEO_ADVICE_STATUS_BROWSER_READY = "browser_ready"
VIDEO_ADVICE_STATUS_LAUNCHER_RECOMMENDED = "launcher_recommended"
VIDEO_ADVICE_STATUS_UNKNOWN = "unknown"
ARTCLASS_PRIMARY_PLAYBACK_MODE = ArtClass.PLAYBACK_MODE_EXTERNAL_WINDOW

ARTCLASS_GEMINI_EXAMPLE_RESULT = json.dumps(
    {
        "video_title": "봄 꽃병 꾸미기",
        "steps": [
            {
                "summary": "꽃병 바탕색을 먼저 정하고 큰 면부터 채운다.",
                "materials": ["도화지", "사인펜"],
                "teacher_tip": "큰 색면을 먼저 정하면 아이들이 이후 장식 구성을 더 쉽게 따라온다.",
            },
            {
                "summary": "꽃과 잎 장식을 더해 화면을 채운다.",
                "materials": ["색종이", "풀"],
                "teacher_tip": "장식은 세 종류 안에서 반복하게 하면 결과물이 훨씬 정돈돼 보인다.",
            },
            {
                "summary": "작품 제목을 붙이고 서로 감상한다.",
                "teacher_tip": "마무리 때 제목을 먼저 말하게 하면 작품 설명이 자연스럽게 이어진다.",
            },
        ],
    },
    ensure_ascii=False,
    indent=2,
)


def _build_video_advice_payload(status, *, title=""):
    resolved_title = str(title or "").strip()
    if status == VIDEO_ADVICE_STATUS_BROWSER_READY:
        return {
            "status": VIDEO_ADVICE_STATUS_BROWSER_READY,
            "recommendedMode": ARTCLASS_PRIMARY_PLAYBACK_MODE,
            "headline": "브라우저 재생은 예외 상황에서만 사용합니다",
            "reason": "ArtClass는 런처 기준으로 시작합니다. 브라우저 재생은 별도 대응이 필요할 때만 보조적으로 사용해 주세요.",
            "title": resolved_title,
        }
    if status == VIDEO_ADVICE_STATUS_LAUNCHER_RECOMMENDED:
        return {
            "status": VIDEO_ADVICE_STATUS_LAUNCHER_RECOMMENDED,
            "recommendedMode": ARTCLASS_PRIMARY_PLAYBACK_MODE,
            "headline": "런처로 바로 시작하면 됩니다",
            "reason": "ArtClass는 이제 런처로 수업을 시작합니다. 저장 후 다음 화면의 초록 버튼을 누르면 영상과 수업 안내가 나뉘어 열립니다.",
            "title": resolved_title,
        }
    return {
        "status": VIDEO_ADVICE_STATUS_UNKNOWN,
        "recommendedMode": ARTCLASS_PRIMARY_PLAYBACK_MODE,
        "headline": "유튜브 주소를 넣으면 런처로 바로 시작할 수 있어요",
        "reason": "유효한 유튜브 주소를 확인한 뒤 저장하면 다음 화면에서 런처를 바로 실행할 수 있습니다.",
        "title": resolved_title,
    }


def _build_video_advice(video_url, *, playback_mode="", title_hint=""):
    normalized_url = (video_url or "").strip()
    title = (title_hint or "").strip()
    video_id = _extract_youtube_video_id(normalized_url)

    if not normalized_url or not video_id:
        return _build_video_advice_payload(VIDEO_ADVICE_STATUS_UNKNOWN, title=title)

    if not title:
        title = _fetch_youtube_title(normalized_url)

    return _build_video_advice_payload(VIDEO_ADVICE_STATUS_LAUNCHER_RECOMMENDED, title=title)


STEP_FORM_INDEX_RE = re.compile(r"^step_(?:text|existing_id|image)_(\d+)$")
STEP_FORM_INDEX_LIMIT = 200
ARTCLASS_ALLOWED_VIDEO_HOSTS = {"youtube.com", "youtu.be"}
ARTCLASS_ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
}
ARTCLASS_ALLOWED_IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
ARTCLASS_MAX_STEP_IMAGE_BYTES = 5 * 1024 * 1024
ARTCLASS_IMAGE_MIME_TYPES_BY_EXTENSION = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _normalize_int_input(value, *, default, min_value=None, max_value=None):
    if value in (None, ""):
        return default, False

    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default, True

    if min_value is not None and parsed < min_value:
        return default, True
    if max_value is not None and parsed > max_value:
        return default, True
    return parsed, False


def _default_step_interval():
    return int(ArtClass._meta.get_field("default_interval").default)


def _is_allowed_youtube_url(video_url):
    video_url = (video_url or "").strip()
    if not video_url:
        return False
    if not _extract_youtube_video_id(video_url):
        return False
    try:
        hostname = (urlparse(video_url).hostname or "").lower().replace("www.", "")
    except Exception:
        hostname = ""
    return hostname in ARTCLASS_ALLOWED_VIDEO_HOSTS or hostname.endswith(".youtube.com")


def _resolve_step_indexes(request):
    indexes = set()
    step_count, corrected = _normalize_int_input(
        request.POST.get("step_count"),
        default=0,
        min_value=0,
        max_value=STEP_FORM_INDEX_LIMIT,
    )
    indexes.update(range(step_count))

    for key in list(request.POST.keys()) + list(request.FILES.keys()):
        matched = STEP_FORM_INDEX_RE.match(key)
        if not matched:
            continue
        step_index = int(matched.group(1))
        if 0 <= step_index < STEP_FORM_INDEX_LIMIT:
            indexes.add(step_index)
        else:
            corrected = True

    return sorted(indexes), corrected


def _build_initial_steps(art_class):
    if not art_class:
        return []
    return [
        {
            'id': step.pk,
            'text': step.description,
            'imagePreview': step.image.url if step.image else None,
        }
        for step in art_class.steps.all()
    ]


def _build_posted_initial_steps(request, art_class=None):
    existing_steps = {}
    if art_class:
        existing_steps = {step.pk: step for step in art_class.steps.all()}

    step_indexes, _ = _resolve_step_indexes(request)
    initial_steps = []
    for step_index in step_indexes:
        existing_step = None
        existing_step_id_raw = (request.POST.get(f"step_existing_id_{step_index}") or "").strip()
        if existing_step_id_raw.isdigit():
            existing_step = existing_steps.get(int(existing_step_id_raw))

        initial_steps.append(
            {
                "id": existing_step.pk if existing_step else None,
                "text": request.POST.get(f"step_text_{step_index}", ""),
                "imagePreview": existing_step.image.url if existing_step and existing_step.image else None,
            }
        )
    return initial_steps


def _validate_step_image(uploaded_image):
    file_name = str(getattr(uploaded_image, "name", "") or "").strip()
    extension = os.path.splitext(file_name)[1].lower()
    content_type = str(getattr(uploaded_image, "content_type", "") or "").lower()
    file_size = int(getattr(uploaded_image, "size", 0) or 0)

    if file_size > ARTCLASS_MAX_STEP_IMAGE_BYTES:
        return "단계 이미지는 5MB 이하만 업로드할 수 있어요."
    if extension not in ARTCLASS_ALLOWED_IMAGE_EXTENSIONS:
        return "단계 이미지는 JPG, PNG, GIF, WEBP 파일만 사용할 수 있어요."
    if content_type and content_type not in ARTCLASS_ALLOWED_IMAGE_CONTENT_TYPES:
        return "단계 이미지는 JPG, PNG, GIF, WEBP 파일만 사용할 수 있어요."

    current_position = None
    try:
        current_position = uploaded_image.tell()
    except Exception:
        current_position = None

    try:
        uploaded_image.seek(0)
        with Image.open(uploaded_image) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        return "손상되었거나 지원하지 않는 이미지 파일입니다. JPG, PNG, GIF, WEBP만 사용해 주세요."
    finally:
        try:
            uploaded_image.seek(0 if current_position is None else current_position)
        except Exception:
            pass

    return ""


def _guess_step_image_mime_type(image_name):
    extension = os.path.splitext(str(image_name or "").strip())[1].lower()
    return ARTCLASS_IMAGE_MIME_TYPES_BY_EXTENSION.get(extension, "image/png")


def _build_launcher_safe_step_image_url(step):
    if not step.image:
        return None

    try:
        step.image.open("rb")
        image_bytes = step.image.read()
    except Exception:
        return None
    finally:
        try:
            step.image.close()
        except Exception:
            pass

    if not image_bytes:
        return None

    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    mime_type = _guess_step_image_mime_type(step.image.name)
    return f"data:{mime_type};base64,{encoded_image}"


def _build_setup_context(art_class=None, *, initial_steps=None, initial_playback_mode=None, setup_video_url=""):
    initial_steps = initial_steps if initial_steps is not None else _build_initial_steps(art_class)
    selected_mode = ARTCLASS_PRIMARY_PLAYBACK_MODE
    video_url = setup_video_url if setup_video_url is not None else (art_class.youtube_url if art_class else "")
    video_advice = _build_video_advice(
        video_url,
        playback_mode=selected_mode,
        title_hint=art_class.title if art_class else "",
    )

    return {
        'art_class': art_class,
        'initial_steps': initial_steps,
        'initial_playback_mode': selected_mode,
        'video_advice': video_advice,
        'manual_prompt_template': build_manual_pipeline_prompt(video_url),
        'launcher_download_url': _get_launcher_download_url(),
        'gemini_example_result': ARTCLASS_GEMINI_EXAMPLE_RESULT,
        'setup_video_url': video_url,
    }


def _render_setup_page(request, art_class=None, **kwargs):
    return render(request, 'artclass/setup.html', _build_setup_context(art_class, **kwargs))


def _resolve_setup_title(posted_title, art_class):
    if posted_title is None and art_class:
        return art_class.title
    return (posted_title or "").strip()


@ratelimit(key=ratelimit_key_for_master_only, rate='24/10m', method='POST', block=True, group='artclass_setup_submit')
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
        video_url = (request.POST.get('videoUrl', '') or '').strip()
        interval_default = art_class.default_interval if art_class else _default_step_interval()
        interval, interval_corrected = _normalize_int_input(
            request.POST.get('stepInterval'),
            default=interval_default,
            min_value=5,
            max_value=3600,
        )
        posted_title = request.POST.get('title')
        title = _resolve_setup_title(posted_title, art_class)
        playback_mode = ARTCLASS_PRIMARY_PLAYBACK_MODE
        auto_corrected = interval_corrected

        if not _is_allowed_youtube_url(video_url):
            messages.error(request, "유효한 유튜브 주소만 사용할 수 있어요. 유튜브 영상 링크를 다시 확인해 주세요.")
            return _render_setup_page(
                request,
                art_class,
                initial_steps=_build_posted_initial_steps(request, art_class),
                initial_playback_mode=playback_mode,
                setup_video_url=video_url,
            )

        for key, uploaded_image in request.FILES.items():
            if not STEP_FORM_INDEX_RE.match(key):
                continue
            image_error = _validate_step_image(uploaded_image)
            if image_error:
                messages.error(request, image_error)
                return _render_setup_page(
                    request,
                    art_class,
                    initial_steps=_build_posted_initial_steps(request, art_class),
                    initial_playback_mode=playback_mode,
                    setup_video_url=video_url,
                )
        
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
        step_indexes, step_input_corrected = _resolve_step_indexes(request)
        auto_corrected = auto_corrected or step_input_corrected
        step_payloads = []
        for step_number, step_index in enumerate(step_indexes, start=1):
            description = request.POST.get(f'step_text_{step_index}', '')
            uploaded_image = request.FILES.get(f'step_image_{step_index}')
            image_value = uploaded_image

            if not image_value:
                existing_step_id_raw = (request.POST.get(f'step_existing_id_{step_index}') or '').strip()
                if existing_step_id_raw.isdigit():
                    existing_step_id = int(existing_step_id_raw)
                    image_value = existing_step_image_names.get(existing_step_id)

            step_payloads.append(
                {
                    'step_number': step_number,
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

        apply_auto_metadata(art_class)

        if auto_corrected:
            messages.info(request, "입력 일부를 자동 보정했습니다. 그대로 시작 가능합니다.")
         
        classroom_url = f"{reverse('artclass:classroom', kwargs={'pk': art_class.pk})}?{urlencode({'autostart_launcher': '1'})}"
        return redirect(classroom_url)
    
    return _render_setup_page(request, art_class)


def classroom_view(request, pk):
    """Classroom Page - 수업 진행 페이지"""
    art_class = get_object_or_404(ArtClass, pk=pk)
    display_mode = "dashboard" if request.GET.get("display") == "dashboard" else "classroom"
    runtime_mode = "launcher" if request.GET.get("runtime") == "launcher" else "web"
    can_manage_classroom = _can_manage_art_class(request.user, art_class)
    effective_playback_mode = ARTCLASS_PRIMARY_PLAYBACK_MODE
    should_inline_step_images = runtime_mode == "launcher" and display_mode == "dashboard"
    
    # 조회수 증가
    art_class.view_count += 1
    update_fields = ['view_count']
    if art_class.playback_mode != effective_playback_mode:
        art_class.playback_mode = effective_playback_mode
        update_fields.append('playback_mode')
    art_class.save(update_fields=update_fields)
    
    steps = art_class.steps.all()
    
    # JSON 형태로 전달 (JS에서 사용)
    steps_data = [
        {
            'id': step.pk,
            'step_number': step.step_number,
            'text': step.description,
            'image_url': (
                _build_launcher_safe_step_image_url(step)
                if should_inline_step_images
                else (step.image.url if step.image else None)
            ),
        }
        for step in steps
    ]
    
    video_advice = _build_video_advice(
        art_class.youtube_url,
        playback_mode=effective_playback_mode,
        title_hint=art_class.title,
    )
    data = {
        'videoUrl': art_class.youtube_url,
        'stepInterval': art_class.default_interval,
        'playbackMode': effective_playback_mode,
        'steps': steps_data,
        'videoAdvice': video_advice,
    }
    
    return render(request, 'artclass/classroom.html', {
        'art_class': art_class,
        'steps': steps,
        'data': data,
        'data_json': json.dumps(data, ensure_ascii=False),
        'can_manage_classroom': can_manage_classroom,
        'display_mode': display_mode,
        'runtime_mode': runtime_mode,
        'video_advice': video_advice,
        'launcher_download_url': _get_launcher_download_url(),
    })


@require_POST
def update_step_text_api(request, pk, step_id):
    """현재 수업 단계 텍스트를 업데이트한다."""
    art_class = get_object_or_404(ArtClass, pk=pk)
    step = get_object_or_404(ArtStep, pk=step_id, art_class=art_class)

    if not request.user.is_authenticated:
        return JsonResponse({"error": "AUTH_REQUIRED", "message": "로그인이 필요합니다."}, status=401)
    if not _can_manage_art_class(request.user, art_class):
        return JsonResponse({"error": "FORBIDDEN", "message": "이 수업 단계를 저장할 권한이 없습니다."}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "INVALID_JSON", "message": "요청 형식이 올바르지 않습니다."}, status=400)

    text = str(payload.get("text") or "").strip()
    if not text:
        return JsonResponse({"error": "EMPTY_TEXT", "message": "단계 설명은 비워둘 수 없습니다."}, status=400)
    if len(text) > 5000:
        return JsonResponse({"error": "TEXT_TOO_LONG", "message": "단계 설명이 너무 깁니다."}, status=400)

    if step.description != text:
        step.description = text
        step.save(update_fields=["description"])

    return JsonResponse(
        {
            "success": True,
            "stepId": step.pk,
            "text": step.description,
        }
    )


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
    if mode != ARTCLASS_PRIMARY_PLAYBACK_MODE:
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

    if art_class.playback_mode != ARTCLASS_PRIMARY_PLAYBACK_MODE:
        art_class.playback_mode = ARTCLASS_PRIMARY_PLAYBACK_MODE
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


@ratelimit(key=ratelimit_key_for_master_only, rate='180/10m', method='POST', block=True, group='artclass_video_advice')
@require_POST
def video_advice_api(request):
    """유튜브 주소 기준으로 브라우저/런처 권장 상태를 반환한다."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "INVALID_JSON", "message": "요청 형식이 올바르지 않습니다."}, status=400)

    video_url = str(payload.get("videoUrl") or "").strip()
    advice = _build_video_advice(video_url)
    return JsonResponse(advice)


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
        return JsonResponse({'error': 'EMPTY_INPUT', 'message': '답변을 붙여넣어 주세요.'}, status=400)

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
    query = (request.GET.get('q') or '').strip()
    selected_category = (request.GET.get('category') or '').strip()
    selected_grade = (request.GET.get('grade') or '').strip()
    selected_tag = (request.GET.get('tag') or '').strip()
    my_classes = []

    if request.user.is_authenticated:
        my_classes = list(
            ArtClass.objects.select_related('created_by', 'created_by__userprofile')
            .annotate(steps_count=Count('steps'))
            .filter(created_by=request.user)
            .distinct()
        )
        for item in my_classes:
            item.creator_display_name = _resolve_creator_display_name(item.created_by)
            item.start_mode_badge = "런처 시작"
            item.start_mode_reason = "이 수업은 런처로 시작합니다."
            item.primary_action_label = "런처로 수업 시작하기"

    shared_classes = ArtClass.objects.select_related('created_by', 'created_by__userprofile').annotate(
        steps_count=Count('steps')
    ).filter(is_shared=True)

    if query:
        shared_classes = shared_classes.filter(
            Q(title__icontains=query)
            | Q(search_text__icontains=query)
            | Q(steps__description__icontains=query)
        )

    if selected_category:
        shared_classes = shared_classes.filter(auto_category=selected_category)

    if selected_grade:
        shared_classes = shared_classes.filter(auto_grade_band=selected_grade)

    if selected_tag:
        shared_classes = shared_classes.filter(search_text__icontains=selected_tag)

    shared_classes = list(shared_classes.distinct())
    for item in shared_classes:
        item.creator_display_name = _resolve_creator_display_name(item.created_by)
        item.start_mode_badge = "런처 시작"
        item.start_mode_reason = "이 수업은 런처로 시작합니다."
        item.primary_action_label = "런처로 수업 시작하기"

    shared_only = ArtClass.objects.filter(is_shared=True)
    category_options = list(
        shared_only.exclude(auto_category='')
        .values_list('auto_category', flat=True)
        .order_by('auto_category')
        .distinct()
    )
    grade_options = list(
        shared_only.exclude(auto_grade_band='')
        .values_list('auto_grade_band', flat=True)
        .order_by('auto_grade_band')
        .distinct()
    )
    popular_tags = collect_popular_tags(shared_only)

    return render(request, 'artclass/library.html', {
        'my_classes': my_classes,
        'shared_classes': shared_classes,
        'query': query,
        'selected_category': selected_category,
        'selected_grade': selected_grade,
        'selected_tag': selected_tag,
        'category_options': category_options,
        'grade_options': grade_options,
        'popular_tags': popular_tags,
        'launcher_download_url': _get_launcher_download_url(),
    })


@login_required
def clone_for_edit_view(request, pk):
    """공유 수업을 내 수업으로 복사한 뒤 수정 화면으로 이동한다."""
    source = get_object_or_404(ArtClass.objects.prefetch_related("steps"), pk=pk)

    if _can_manage_art_class(request.user, source):
        return redirect("artclass:setup_edit", pk=source.pk)

    if not source.is_shared:
        raise PermissionDenied("이 수업을 복사할 권한이 없습니다.")

    cloned = ArtClass.objects.create(
        title=source.title,
        youtube_url=source.youtube_url,
        default_interval=source.default_interval,
        playback_mode=ARTCLASS_PRIMARY_PLAYBACK_MODE,
        created_by=request.user,
        is_shared=source.is_shared,
    )

    for step in source.steps.all():
        ArtStep.objects.create(
            art_class=cloned,
            step_number=step.step_number,
            description=step.description,
            image=step.image.name if step.image else None,
        )

    apply_auto_metadata(cloned)
    messages.success(request, "수업을 내 수업으로 복사했습니다. 원하는 대로 수정해 주세요.")
    return redirect("artclass:setup_edit", pk=cloned.pk)


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
