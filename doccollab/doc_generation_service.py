import re

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .doc_generation_llm import (
    DOCUMENT_PROMPT_VERSION,
    DOCUMENT_TYPE_LABELS,
    MAX_PROMPT_CHARS,
    MIN_PROMPT_CHARS,
    generate_document_content,
)
from .doc_hwp_builder import build_document_hwpx_bytes, document_hwpx_file_name
from .document_spec import normalize_document_spec, normalize_feature_codes, validate_document_spec
from .models import DocGeneratedDraft, DocMembership, DocRevision, DocRoom, DocWorkspace
from .services import save_room_revision


DEFAULT_DOCUMENT_DAILY_LIMIT = 5
DAILY_LIMIT_CACHE_TTL = 86410


def document_daily_limit_per_user():
    return max(int(getattr(settings, "DOCCOLLAB_DOCUMENT_DAILY_LIMIT", DEFAULT_DOCUMENT_DAILY_LIMIT)), 0)


def document_daily_limit_cache_key(user_id):
    return f"doccollab:document:draft:daily:{user_id}:{timezone.localdate().isoformat()}"


def document_daily_limit_used(user_id):
    current = cache.get(document_daily_limit_cache_key(user_id)) or 0
    try:
        return max(int(current), 0)
    except (TypeError, ValueError):
        return 0


def document_daily_limit_message(limit=None):
    effective_limit = document_daily_limit_per_user() if limit is None else max(int(limit), 0)
    return f"오늘 문서 {effective_limit}개를 모두 사용했습니다."


def reserve_document_daily_limit(user_id):
    limit = document_daily_limit_per_user()
    if limit <= 0:
        return False
    if document_daily_limit_used(user_id) >= limit:
        return False
    cache_key = document_daily_limit_cache_key(user_id)
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


def release_document_daily_limit(user_id):
    cache_key = document_daily_limit_cache_key(user_id)
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


def validate_document_generation_request(*, document_type, prompt, selected_blocks=None):
    normalized_type = str(document_type or "").strip() or DocGeneratedDraft.DocumentType.FREEFORM
    normalized_prompt = re.sub(r"\s+", " ", str(prompt or "").strip())
    if normalized_type not in DOCUMENT_TYPE_LABELS:
        raise ValidationError("지원하지 않는 문서 종류입니다.")
    if len(normalized_prompt) < MIN_PROMPT_CHARS:
        raise ValidationError("요청 내용을 20자 이상 적어 주세요.")
    if len(normalized_prompt) > MAX_PROMPT_CHARS:
        raise ValidationError("요청 내용은 2000자 안쪽으로 적어 주세요.")
    return normalized_type, normalized_prompt, normalize_feature_codes(selected_blocks)


def document_content_json_from_payload(payload):
    source = payload if isinstance(payload, dict) else {}
    return normalize_document_spec(
        source,
        document_type=source.get("document_type") or DocGeneratedDraft.DocumentType.FREEFORM,
        prompt=source.get("summary_text") or source.get("title") or "학교 실무 문서 초안",
        selected_blocks=source.get("selected_blocks"),
    )


def create_generated_document_room(*, user, document_type, prompt, selected_blocks=None):
    normalized_type, normalized_prompt, normalized_blocks = validate_document_generation_request(
        document_type=document_type,
        prompt=prompt,
        selected_blocks=selected_blocks,
    )
    room, draft = _create_draft_shell(user=user, document_type=normalized_type, prompt=normalized_prompt)
    try:
        payload = generate_document_content(
            document_type=normalized_type,
            prompt=normalized_prompt,
            selected_blocks=normalized_blocks,
        )
        payload = normalize_document_spec(
            payload,
            document_type=normalized_type,
            prompt=normalized_prompt,
            selected_blocks=normalized_blocks,
        )
        issues = validate_document_spec(payload)
        if issues:
            raise ValidationError(issues[0])
        generated = build_document_hwpx_bytes(content=payload)
        build_issues = validate_document_spec(payload, page_count=max(int(generated.get("page_count") or 0), 0))
        if build_issues:
            raise ValidationError(build_issues[0])
        revision = _complete_generated_document(
            user=user,
            room=room,
            draft=draft,
            payload=payload,
            generated=generated,
        )
    except Exception as exc:
        _mark_draft_failed(draft=draft, message=str(exc) or "문서 생성 실패")
        raise
    draft.refresh_from_db()
    room.refresh_from_db()
    return room, draft, revision


@transaction.atomic
def _create_draft_shell(*, user, document_type, prompt):
    label = DOCUMENT_TYPE_LABELS.get(document_type, DOCUMENT_TYPE_LABELS["freeform"])
    title = f"{label} 초안"
    workspace = DocWorkspace.objects.create(
        name=title,
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
        title=title,
        created_by=user,
        origin_kind=DocRoom.OriginKind.AI_DRAFT,
        source_name="",
        source_format=DocRoom.SourceFormat.HWPX,
        source_sha256="",
        last_activity_at=timezone.now(),
    )
    draft = DocGeneratedDraft.objects.create(
        room=room,
        document_type=document_type,
        request_text=prompt,
        status=DocGeneratedDraft.Status.BUILDING,
        provider="deepseek",
        prompt_version=DOCUMENT_PROMPT_VERSION,
    )
    return room, draft


@transaction.atomic
def _complete_generated_document(*, user, room, draft, payload, generated):
    room_title = str(payload.get("title") or room.title).strip()[:200] or room.title
    room.title = room_title
    room.last_activity_at = timezone.now()
    room.save(update_fields=["title", "last_activity_at", "updated_at"])
    room.workspace.name = room_title
    room.workspace.status = DocWorkspace.Status.ACTIVE
    room.workspace.save(update_fields=["name", "status", "updated_at"])
    room.workspace.memberships.update(status=DocMembership.Status.ACTIVE)

    revision = save_room_revision(
        room=room,
        user=user,
        uploaded_file=ContentFile(
            generated["hwpx_bytes"],
            name=generated.get("file_name") or document_hwpx_file_name(room_title),
        ),
        export_format=DocRevision.ExportFormat.HWPX_EXPORT,
        note="AI 문서 초안 생성",
    )
    draft.status = DocGeneratedDraft.Status.READY
    draft.content_json = document_content_json_from_payload(payload)
    draft.summary_text = payload.get("summary_text") or ""
    draft.error_message = ""
    draft.latest_page_count = max(int(generated.get("page_count") or 1), 1)
    draft.provider = "deepseek"
    draft.prompt_version = DOCUMENT_PROMPT_VERSION
    draft.save(
        update_fields=[
            "status",
            "content_json",
            "summary_text",
            "error_message",
            "latest_page_count",
            "provider",
            "prompt_version",
            "updated_at",
        ]
    )
    return revision


@transaction.atomic
def _mark_draft_failed(*, draft, message):
    error_message = str(message or "문서 생성 실패").strip()[:200]
    DocGeneratedDraft.objects.filter(id=draft.id).update(
        status=DocGeneratedDraft.Status.FAILED,
        error_message=error_message,
        updated_at=timezone.now(),
    )
    DocRoom.objects.filter(id=draft.room_id).update(
        status=DocRoom.Status.ARCHIVED,
        updated_at=timezone.now(),
    )
    DocWorkspace.objects.filter(id=draft.room.workspace_id).update(
        status=DocWorkspace.Status.ARCHIVED,
        updated_at=timezone.now(),
    )
    DocMembership.objects.filter(workspace_id=draft.room.workspace_id).update(
        status=DocMembership.Status.DISABLED,
        updated_at=timezone.now(),
    )
