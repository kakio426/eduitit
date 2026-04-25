import re

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import DocMembership, DocRevision, DocRoom, DocWorkspace, DocWorksheet
from .services import publish_revision, save_room_revision
from .worksheet_hwp_builder import WORKSHEET_LAYOUT_PROFILES, WorksheetBuildError, build_worksheet_hwpx_bytes
from .worksheet_llm import WORKSHEET_PROMPT_VERSION, generate_worksheet_content


DEFAULT_DAILY_LIMIT = 3
DAILY_LIMIT_CACHE_TTL = 86410


def worksheet_daily_limit_per_user():
    return max(int(getattr(settings, "DOCCOLLAB_WORKSHEET_DAILY_LIMIT", DEFAULT_DAILY_LIMIT)), 0)


def worksheet_daily_limit_cache_key(user_id):
    return f"doccollab:worksheet:daily:{user_id}:{timezone.localdate().isoformat()}"


def worksheet_daily_limit_used(user_id):
    current = cache.get(worksheet_daily_limit_cache_key(user_id)) or 0
    try:
        return max(int(current), 0)
    except (TypeError, ValueError):
        return 0


def worksheet_daily_limit_message(limit=None):
    effective_limit = worksheet_daily_limit_per_user() if limit is None else max(int(limit), 0)
    return f"오늘 학습지 {effective_limit}장을 모두 사용했어요. 내일 다시 만들어 볼까요?"


def reserve_worksheet_daily_limit(user_id):
    limit = worksheet_daily_limit_per_user()
    if limit <= 0:
        return False
    if worksheet_daily_limit_used(user_id) >= limit:
        return False
    cache_key = worksheet_daily_limit_cache_key(user_id)
    current = cache.get(cache_key)
    if current is None:
        cache.set(cache_key, 1, timeout=DAILY_LIMIT_CACHE_TTL)
        return True
    try:
        current = cache.incr(cache_key)
    except Exception:
        current = int(current) + 1
        cache.set(cache_key, current, timeout=DAILY_LIMIT_CACHE_TTL)
    return int(current) <= limit


def release_worksheet_daily_limit(user_id):
    cache_key = worksheet_daily_limit_cache_key(user_id)
    current = cache.get(cache_key)
    if current is None:
        return
    try:
        current = int(current)
    except (TypeError, ValueError):
        current = 0
    if current <= 1:
        cache.delete(cache_key)
        return
    cache.set(cache_key, current - 1, timeout=DAILY_LIMIT_CACHE_TTL)


def worksheet_content_json_from_payload(payload):
    return {
        "title": payload.get("title") or "",
        "companion_line": payload.get("companion_line") or "",
        "curiosity_opening": payload.get("curiosity_opening") or "",
        "key_points": list(payload.get("key_points") or [])[:3],
        "quiz_items": list(payload.get("quiz_items") or [])[:2],
    }


def public_worksheet_queryset():
    return (
        DocWorksheet.objects.select_related("room", "room__created_by", "room__workspace", "source_worksheet", "source_worksheet__room")
        .prefetch_related("room__revisions")
        .filter(
            is_library_published=True,
            bootstrap_status=DocWorksheet.BootstrapStatus.READY,
            room__status=DocRoom.Status.ACTIVE,
            room__workspace__status=DocWorkspace.Status.ACTIVE,
        )
        .order_by("-updated_at", "-created_at")
    )


def owned_worksheet_queryset(user):
    return (
        DocWorksheet.objects.select_related("room", "room__created_by", "room__workspace", "source_worksheet")
        .prefetch_related("room__revisions")
        .filter(
            room__created_by=user,
            room__status=DocRoom.Status.ACTIVE,
            room__workspace__status=DocWorkspace.Status.ACTIVE,
        )
        .order_by("-updated_at", "-created_at")
    )


def generate_single_page_worksheet(*, topic):
    normalized_topic = str(topic or "").strip()
    if not normalized_topic:
        raise ValidationError("학습 주제를 먼저 입력해 주세요.")

    payload = generate_worksheet_content(topic=normalized_topic, force_short=False)
    attempted_short = False

    while True:
        last_result = None
        for layout_profile in WORKSHEET_LAYOUT_PROFILES:
            last_result = build_worksheet_hwpx_bytes(content=payload, layout_profile=layout_profile)
            if max(int(last_result.get("page_count") or 0), 0) <= 1:
                return {
                    "content": payload,
                    "hwpx_bytes": last_result["hwpx_bytes"],
                    "page_count": 1,
                    "used_profile": layout_profile,
                    "file_name": last_result.get("file_name") or worksheet_hwpx_file_name(payload.get("title") or normalized_topic),
                }
        if attempted_short:
            final_page_count = max(int((last_result or {}).get("page_count") or 0), 0)
            raise WorksheetBuildError(
                f"학습지를 한 장으로 맞추지 못했습니다. 현재 {max(final_page_count, 2)}페이지로 계산됐습니다."
            )
        attempted_short = True
        payload = generate_worksheet_content(topic=normalized_topic, force_short=True)


def worksheet_hwpx_file_name(title):
    stem = re.sub(r"[\s]+", " ", str(title or "").strip()).strip()
    stem = re.sub(r'[\\/:*?"<>|]+', " ", stem).strip()[:80] or "worksheet"
    return f"{stem}.hwpx"


def worksheet_hwp_file_name(title):
    return worksheet_hwpx_file_name(title)


@transaction.atomic
def create_generated_worksheet_room(*, user, topic):
    normalized_topic = str(topic or "").strip()
    if not normalized_topic:
        raise ValidationError("학습 주제를 먼저 입력해 주세요.")
    if len(normalized_topic) > 120:
        raise ValidationError("학습 주제는 120자 안쪽으로 적어 주세요.")

    generated = generate_single_page_worksheet(topic=normalized_topic)
    payload = generated["content"]
    room_title = str(payload.get("title") or f"{normalized_topic} 학습지").strip()[:200]
    workspace = DocWorkspace.objects.create(
        name=room_title,
        created_by=user,
    )
    DocMembership.objects.create(
        workspace=workspace,
        user=user,
        role=DocMembership.Role.OWNER,
        status=DocMembership.Status.ACTIVE,
        invited_by=user,
    )
    room = DocRoom.objects.create(
        workspace=workspace,
        title=room_title,
        created_by=user,
        origin_kind=DocRoom.OriginKind.GENERATED_WORKSHEET,
        source_name="",
        source_format=DocRoom.SourceFormat.HWPX,
        source_sha256="",
        last_activity_at=timezone.now(),
    )
    revision = save_room_revision(
        room=room,
        user=user,
        uploaded_file=ContentFile(
            generated["hwpx_bytes"],
            name=generated.get("file_name") or worksheet_hwpx_file_name(room_title),
        ),
        export_format=DocRevision.ExportFormat.HWPX_EXPORT,
        note="학습지 초안 생성",
    )
    worksheet = DocWorksheet.objects.create(
        room=room,
        topic=normalized_topic,
        summary_text=payload.get("summary_text") or "",
        content_json=worksheet_content_json_from_payload(payload),
        search_text=payload.get("search_text") or "",
        provider="deepseek",
        prompt_version=WORKSHEET_PROMPT_VERSION,
        latest_page_count=max(int(generated.get("page_count") or 1), 1),
        bootstrap_status=DocWorksheet.BootstrapStatus.READY,
    )
    return room, worksheet, revision


@transaction.atomic
def publish_generated_worksheet(*, worksheet):
    current_revision = worksheet.room.revisions.order_by("-revision_number").first()
    if current_revision is None:
        raise ValidationError("먼저 학습지를 저장해 주세요.")
    if worksheet.bootstrap_status != DocWorksheet.BootstrapStatus.READY:
        raise ValidationError("학습지 준비가 끝난 뒤에 공개할 수 있습니다.")
    publish_revision(worksheet.room, current_revision)
    worksheet.is_library_published = True
    worksheet.save(update_fields=["is_library_published", "updated_at"])
    return current_revision


@transaction.atomic
def clone_published_worksheet(*, worksheet, user):
    if not worksheet.is_library_published or worksheet.bootstrap_status != DocWorksheet.BootstrapStatus.READY:
        raise ValidationError("가져올 수 있는 공개 학습지가 아닙니다.")

    published_revision = worksheet.room.revisions.filter(is_published=True).order_by("-revision_number").first()
    if published_revision is None:
        raise ValidationError("공개된 저장본을 찾지 못했습니다.")

    with published_revision.file.open("rb") as handle:
        raw_bytes = handle.read()

    clone_title = worksheet.room.title[:200]
    workspace = DocWorkspace.objects.create(
        name=clone_title,
        created_by=user,
    )
    DocMembership.objects.create(
        workspace=workspace,
        user=user,
        role=DocMembership.Role.OWNER,
        status=DocMembership.Status.ACTIVE,
        invited_by=user,
    )
    room = DocRoom.objects.create(
        workspace=workspace,
        title=clone_title,
        created_by=user,
        origin_kind=DocRoom.OriginKind.GENERATED_WORKSHEET,
        source_name="",
        source_format=DocRoom.SourceFormat.HWPX,
        source_sha256="",
        last_activity_at=timezone.now(),
    )
    upload = ContentFile(raw_bytes, name=published_revision.original_name or worksheet_hwpx_file_name(clone_title))
    revision = save_room_revision(
        room=room,
        user=user,
        uploaded_file=upload,
        export_format=DocRevision.ExportFormat.HWPX_EXPORT,
        note="공개 학습지 가져오기",
    )
    cloned = DocWorksheet.objects.create(
        room=room,
        source_worksheet=worksheet,
        topic=worksheet.topic,
        summary_text=worksheet.summary_text,
        content_json=worksheet.content_json,
        search_text=worksheet.search_text,
        provider=worksheet.provider,
        prompt_version=worksheet.prompt_version,
        latest_page_count=max(worksheet.latest_page_count, 1),
        bootstrap_status=DocWorksheet.BootstrapStatus.READY,
        is_library_published=False,
    )
    return room, cloned, revision


def worksheet_is_publicly_accessible(room):
    worksheet = getattr(room, "worksheet", None)
    return bool(
        worksheet
        and worksheet.is_library_published
        and worksheet.bootstrap_status == DocWorksheet.BootstrapStatus.READY
        and room.status == DocRoom.Status.ACTIVE
        and room.workspace.status == DocWorkspace.Status.ACTIVE
    )


def worksheet_visible_revision(room, *, public_only=False):
    if public_only and worksheet_is_publicly_accessible(room):
        return room.revisions.filter(is_published=True).order_by("-revision_number").first()
    return room.revisions.order_by("-revision_number").first()
