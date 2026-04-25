import logging
import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.middleware.csrf import get_token
from django.templatetags.static import static as static_url
from django.urls import reverse
from django.utils import formats
from django.utils import timezone

from version_manager.models import Document, DocumentGroup, DocumentVersion

from .models import DocEditEvent, DocMembership, DocPresence, DocRevision, DocRoom, DocSnapshot, DocWorkspace, DocWorksheet

logger = logging.getLogger(__name__)


DOC_GROUP_NAME = "HWP 문서실"
MAX_SOURCE_FILE_BYTES = 20 * 1024 * 1024
MAX_CONTROL_SCAN = 12
MAX_LIVE_UPDATES = 250
MAX_RECENT_BATCH_IDS = 400
SUPPORTED_UPLOAD_FORMATS = {
    ".hwp": DocRoom.SourceFormat.HWP,
    ".hwpx": DocRoom.SourceFormat.HWPX,
}
EDIT_HISTORY_GROUP_WINDOW = timedelta(seconds=90)
EDIT_HISTORY_TEXT_TYPES = {
    "insert_text",
    "delete_text",
    "split_paragraph",
    "merge_paragraph",
    "delete_selection",
    "insert_tab",
}
EDIT_HISTORY_TABLE_TYPES = {
    "set_cell_text",
    "table_cell_text",
    "insert_table_row",
    "insert_table_col",
    "table_row_insert",
    "table_row_delete",
    "table_col_insert",
    "table_col_delete",
}


def compute_sha256(raw_bytes):
    return hashlib.sha256(raw_bytes or b"").hexdigest()


def display_source_format(source_format):
    if source_format == DocRoom.SourceFormat.HWP:
        return "HWP"
    return "HWPX"


def detect_source_format(file_name):
    extension = str(Path(str(file_name or "")).suffix).lower()
    return SUPPORTED_UPLOAD_FORMATS.get(extension)


def file_format_for_revision(revision):
    if revision is None:
        return ""
    if revision.export_format == DocRevision.ExportFormat.SOURCE_HWPX:
        return DocRoom.SourceFormat.HWPX
    return DocRoom.SourceFormat.HWP


def summarize_command(command):
    command = command or {}
    command_type = str(command.get("type") or "edit").strip() or "edit"
    if command_type == "insert_text":
        text = str(command.get("text") or "").replace("\n", " ").strip()
        preview = text[:40]
        summary = f"문장 입력 · {preview}" if preview else "문장 입력"
    elif command_type == "delete_text":
        count = int(command.get("count") or 1)
        summary = f"삭제 · {count}자"
    elif command_type == "split_paragraph":
        summary = "새 문단"
    elif command_type == "merge_paragraph":
        summary = "문단 합치기"
    elif command_type == "delete_selection":
        summary = "선택 삭제"
    elif command_type == "set_cell_text":
        row = int(command.get("row") or 0) + 1
        col = int(command.get("col") or 0) + 1
        text = str(command.get("text") or "").replace("\n", " ").strip()[:30]
        summary = f"표 {row},{col} 셀 수정"
        if text:
            summary = f"{summary} · {text}"
    elif command_type == "table_cell_text":
        row = int(command.get("row") or 0) + 1
        col = int(command.get("col") or 0) + 1
        action = str(command.get("action") or "insert")
        if action == "delete":
            count = int(command.get("count") or 1)
            summary = f"표 {row},{col} 셀 삭제 · {count}자"
        else:
            text = str(command.get("text") or "").replace("\n", " ").strip()[:30]
            summary = f"표 {row},{col} 셀 입력"
            if text:
                summary = f"{summary} · {text}"
    elif command_type == "insert_table_row":
        row = int(command.get("row") or 0) + 1
        summary = f"표 {row}행 추가"
    elif command_type == "insert_table_col":
        col = int(command.get("col") or 0) + 1
        summary = f"표 {col}열 추가"
    elif command_type == "table_row_insert":
        row = int(command.get("row") or 0) + 1
        summary = f"표 {row}행 추가"
    elif command_type == "table_row_delete":
        row = int(command.get("row") or 0) + 1
        summary = f"표 {row}행 삭제"
    elif command_type == "table_col_insert":
        col = int(command.get("col") or 0) + 1
        summary = f"표 {col}열 추가"
    elif command_type == "table_col_delete":
        col = int(command.get("col") or 0) + 1
        summary = f"표 {col}열 삭제"
    elif command_type == "save_revision":
        revision_number = int(command.get("revision_number") or 0)
        summary = f"저장본 저장 · r{revision_number}" if revision_number else "저장본 저장"
    elif command_type == "publish_revision":
        revision_number = int(command.get("revision_number") or 0)
        summary = f"배포본 지정 · r{revision_number}" if revision_number else "배포본 지정"
    else:
        summary = "편집"
    return command_type, summary[:200]


def edit_history_family(command_type):
    normalized = str(command_type or "").strip()
    if normalized in EDIT_HISTORY_TEXT_TYPES:
        return "text_edit"
    if normalized in EDIT_HISTORY_TABLE_TYPES:
        return "table_edit"
    if normalized == "save_revision":
        return "save_revision"
    if normalized == "publish_revision":
        return "publish_revision"
    return "edit"


def edit_history_label(command_type):
    family = str(command_type or "").strip() or "edit"
    if family not in {"text_edit", "table_edit", "save_revision", "publish_revision", "edit"}:
        family = edit_history_family(family)
    if family == "text_edit":
        return "본문"
    if family == "table_edit":
        return "표"
    if family == "save_revision":
        return "저장"
    if family == "publish_revision":
        return "배포"
    return "수정"


def _edit_history_summary(family, events):
    count = len(events)
    if family == "text_edit":
        return "본문 수정" if count == 1 else f"본문 수정 {count}건"
    if family == "table_edit":
        return "표 수정" if count == 1 else f"표 수정 {count}건"
    if family == "save_revision":
        return events[0].summary or "저장본 저장"
    if family == "publish_revision":
        return events[0].summary or "배포본 지정"
    return "문서 수정" if count == 1 else f"문서 수정 {count}건"


def _edit_history_timestamp(dt):
    local_dt = timezone.localtime(dt)
    return formats.date_format(local_dt, "Y. n. j. A g:i:s")


def _edit_history_actor_key(event):
    if getattr(event, "user_id", None):
        return f"user:{event.user_id}"
    return f"name:{str(event.display_name or '').strip()}"


def _can_rollup_edit_history(group, event, family):
    if family != group["family"] or family in {"save_revision", "publish_revision"}:
        return False
    if _edit_history_actor_key(event) != group["actor_key"]:
        return False
    oldest_at = group.get("oldest_at")
    if oldest_at is None or event.created_at is None:
        return False
    return (oldest_at - event.created_at) <= EDIT_HISTORY_GROUP_WINDOW


def _serialize_edit_history_group(group):
    newest_event = group["events"][0]
    family = group["family"]
    return {
        "id": f"group:{newest_event.id}",
        "command_type": family,
        "command_label": edit_history_label(family),
        "display_name": newest_event.display_name,
        "summary": _edit_history_summary(family, group["events"]),
        "event_count": len(group["events"]),
        "created_at": newest_event.created_at.isoformat(),
        "created_at_display": _edit_history_timestamp(newest_event.created_at),
    }


def display_name_for_user(user):
    if user is None:
        return ""
    profile = getattr(user, "userprofile", None)
    nickname = str(getattr(profile, "nickname", "") or "").strip()
    return nickname or user.get_username()


def personal_workspace_name(user):
    return f"{display_name_for_user(user) or '내'} 문서실"


@transaction.atomic
def ensure_personal_workspace(user):
    workspace = (
        DocWorkspace.objects.filter(created_by=user, status=DocWorkspace.Status.ACTIVE)
        .order_by("created_at")
        .first()
    )
    if workspace is None:
        workspace = DocWorkspace.objects.create(
            name=personal_workspace_name(user),
            created_by=user,
        )
    DocMembership.objects.update_or_create(
        workspace=workspace,
        user=user,
        defaults={
            "role": DocMembership.Role.OWNER,
            "status": DocMembership.Status.ACTIVE,
            "invited_by": user,
        },
    )
    return workspace


def room_workspace_name(title, file_name):
    return room_title_from_filename(title, file_name)


def accessible_rooms_queryset(user):
    if not getattr(user, "is_authenticated", False):
        return DocRoom.objects.none()
    return (
        DocRoom.objects.select_related("workspace", "created_by")
        .prefetch_related("workspace__memberships__user", "revisions")
        .filter(
            Q(workspace__memberships__user=user, workspace__memberships__status=DocMembership.Status.ACTIVE)
            | Q(created_by=user)
        )
        .filter(
            workspace__status=DocWorkspace.Status.ACTIVE,
            status=DocRoom.Status.ACTIVE,
        )
        .distinct()
    )


def get_membership_for_workspace(workspace, user):
    return workspace.memberships.filter(user=user, status=DocMembership.Status.ACTIVE).first()


def get_room_for_user(room_id, user):
    room = (
        DocRoom.objects.select_related("workspace", "created_by")
        .prefetch_related("workspace__memberships__user", "revisions")
        .filter(id=room_id)
        .first()
    )
    if room is None:
        return None, None
    if room.status != DocRoom.Status.ACTIVE or room.workspace.status != DocWorkspace.Status.ACTIVE:
        return None, None
    membership = get_membership_for_workspace(room.workspace, user)
    if membership is None and room.created_by_id != getattr(user, "id", None):
        return None, None
    return room, membership


def assert_editor_membership(membership):
    if membership is None:
        raise PermissionDenied("접근 권한이 없습니다.")
    if membership.role not in {DocMembership.Role.OWNER, DocMembership.Role.EDITOR}:
        raise PermissionDenied("편집 권한이 없습니다.")


def assert_owner_membership(membership):
    if membership is None or membership.role != DocMembership.Role.OWNER:
        raise PermissionDenied("관리 권한이 없습니다.")


def room_group_name(room):
    return f"doccollab-room-{room.id}"


def room_collab_state_cache_key(room):
    return f"doccollab:room:{room.id}:live"


def load_room_collab_state(room):
    cached = cache.get(room_collab_state_cache_key(room)) or {}
    if not isinstance(cached, dict):
        cached = {}
    updates = cached.get("updates")
    if not isinstance(updates, list):
        updates = []
    recent_batch_ids = cached.get("recent_batch_ids")
    if not isinstance(recent_batch_ids, list):
        recent_batch_ids = []
    return {
        "base_revision_id": cached.get("base_revision_id"),
        "updates": updates[-MAX_LIVE_UPDATES:],
        "recent_batch_ids": recent_batch_ids[-MAX_RECENT_BATCH_IDS:],
        "updated_at": cached.get("updated_at"),
    }


def reset_room_collab_state(room, *, base_revision=None):
    payload = {
        "base_revision_id": str(base_revision.id) if getattr(base_revision, "id", None) else None,
        "updates": [],
        "recent_batch_ids": [],
        "updated_at": timezone.now().isoformat(),
    }
    cache.set(room_collab_state_cache_key(room), payload, timeout=60 * 60 * 12)
    return payload


def append_room_collab_update(room, update):
    payload = load_room_collab_state(room)
    updates = payload["updates"]
    if isinstance(update, dict):
        updates.append(dict(update))
    else:
        updates.append(list(update or []))
    payload["updates"] = updates[-MAX_LIVE_UPDATES:]
    payload["updated_at"] = timezone.now().isoformat()
    cache.set(room_collab_state_cache_key(room), payload, timeout=60 * 60 * 12)
    return payload


def append_room_command_batch(room, batch):
    payload = load_room_collab_state(room)
    batch_id = str(batch.get("batchId") or "").strip()
    sender_session_key = str(batch.get("senderSessionKey") or "").strip()
    commands = [command for command in (batch.get("commands") or []) if isinstance(command, dict)]
    selection = batch.get("selection") if isinstance(batch.get("selection"), dict) else {}
    if not batch_id:
        return payload, False, "missing batchId"
    if not commands:
        return payload, False, "empty commands"
    recent_batch_ids = payload["recent_batch_ids"]
    if batch_id in recent_batch_ids:
        return payload, False, "duplicate batchId"
    current_base_revision_id = str(payload.get("base_revision_id") or "").strip()
    requested_base_revision_id = str(batch.get("baseRevisionId") or "").strip()
    if current_base_revision_id and requested_base_revision_id and current_base_revision_id != requested_base_revision_id:
        return payload, False, "stale base revision"
    entry = {
        "batchId": batch_id,
        "baseRevisionId": requested_base_revision_id or current_base_revision_id or None,
        "senderSessionKey": sender_session_key,
        "commands": commands,
        "selection": selection,
        "receivedAt": timezone.now().isoformat(),
    }
    updates = payload["updates"]
    updates.append(entry)
    payload["updates"] = updates[-MAX_LIVE_UPDATES:]
    recent_batch_ids.append(batch_id)
    payload["recent_batch_ids"] = recent_batch_ids[-MAX_RECENT_BATCH_IDS:]
    payload["updated_at"] = timezone.now().isoformat()
    cache.set(room_collab_state_cache_key(room), payload, timeout=60 * 60 * 12)
    return payload, True, None


def serialize_presence_list(room):
    return [
        {
            "session_key": item.session_key,
            "display_name": item.display_name,
            "role": item.role,
            "last_seen_at": item.last_seen_at.isoformat(),
        }
        for item in room.presences.filter(is_connected=True).order_by("display_name", "last_seen_at")
    ]


def serialize_revision(revision):
    if revision is None:
        return None
    file_format = file_format_for_revision(revision)
    return {
        "id": str(revision.id),
        "revision_number": revision.revision_number,
        "original_name": revision.original_name,
        "export_format": revision.export_format,
        "export_format_label": revision.ui_export_format_label,
        "file_format": file_format,
        "file_format_label": display_source_format(file_format),
        "is_published": revision.is_published,
        "created_at": revision.created_at.isoformat(),
        "note": revision.note,
        "download_url": reverse(
            "doccollab:download_revision",
            kwargs={"room_id": revision.room_id, "revision_id": revision.id},
        ),
    }


def serialize_edit_event(event):
    return {
        "id": str(event.id),
        "command_id": event.command_id,
        "command_type": event.command_type,
        "command_label": edit_history_label(event.command_type),
        "display_name": event.display_name,
        "summary": event.summary,
        "created_at": event.created_at.isoformat(),
    }


def serialize_edit_history(room, *, limit=10):
    raw_limit = max(limit * 20, 80)
    raw_events = list(room.edit_events.select_related("user").order_by("-created_at")[:raw_limit])
    groups = []
    current_group = None
    for event in raw_events:
        family = edit_history_family(event.command_type)
        if current_group and _can_rollup_edit_history(current_group, event, family):
            current_group["events"].append(event)
            current_group["oldest_at"] = event.created_at
            continue
        if current_group is not None:
            groups.append(_serialize_edit_history_group(current_group))
            if len(groups) >= limit:
                return groups
        current_group = {
            "family": family,
            "actor_key": _edit_history_actor_key(event),
            "events": [event],
            "oldest_at": event.created_at,
        }
    if current_group is not None and len(groups) < limit:
        groups.append(_serialize_edit_history_group(current_group))
    return groups


def serialize_room(room, membership=None):
    current_revision = room.revisions.order_by("-revision_number").first()
    published_revision = room.revisions.filter(is_published=True).order_by("-revision_number").first()
    return {
        "id": str(room.id),
        "title": room.title,
        "workspace_name": room.workspace.name,
        "source_name": room.source_name,
        "source_format": room.source_format,
        "source_format_label": room.get_source_format_display(),
        "last_activity_at": room.last_activity_at.isoformat(),
        "membership_role": getattr(membership, "role", ""),
        "current_revision": serialize_revision(current_revision) if current_revision else None,
        "published_revision": serialize_revision(published_revision) if published_revision else None,
        "presence": serialize_presence_list(room),
        "edit_history": serialize_edit_history(room),
        "collab_state": load_room_collab_state(room),
    }


def read_uploaded_file(uploaded_file):
    if uploaded_file is None:
        raise ValidationError("파일을 선택해 주세요.")
    name = str(getattr(uploaded_file, "name", "") or "").strip()
    source_format = detect_source_format(name)
    if source_format is None:
        raise ValidationError("HWP 또는 HWPX 파일만 올릴 수 있습니다.")
    raw_bytes = uploaded_file.read()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    if not raw_bytes:
        raise ValidationError("빈 파일은 올릴 수 없습니다.")
    if len(raw_bytes) > MAX_SOURCE_FILE_BYTES:
        raise ValidationError("파일이 너무 큽니다. 20MB 이하 HWP/HWPX만 지원합니다.")
    return name, raw_bytes, source_format


def room_title_from_filename(title, file_name):
    normalized = str(title or "").strip()
    if normalized:
        return normalized[:200]
    return (Path(file_name).stem or "새 문서")[:200]


def _next_revision_number(room):
    current = room.revisions.aggregate(max_revision=Max("revision_number")).get("max_revision") or 0
    return int(current) + 1


def _unique_document_base_name(group, desired_name):
    base = str(desired_name or "").strip()[:200] or "문서"
    candidate = base
    suffix = 2
    while Document.objects.filter(group=group, base_name=candidate).exists():
        suffix_text = f" ({suffix})"
        candidate = f"{base[: max(1, 200 - len(suffix_text))]}{suffix_text}"
        suffix += 1
    return candidate


def _mirror_revision(room, revision, raw_bytes, user):
    group, _ = DocumentGroup.objects.get_or_create(name=DOC_GROUP_NAME)
    document = room.mirrored_document
    if document is None:
        document = Document.objects.create(
            group=group,
            base_name=_unique_document_base_name(group, room.title),
        )
        room.mirrored_document = document
        room.save(update_fields=["mirrored_document"])
    next_version = (document.versions.aggregate(max_version=Max("version")).get("max_version") or 0) + 1
    mirrored = DocumentVersion.objects.create(
        document=document,
        version=next_version,
        upload=ContentFile(raw_bytes, name=revision.original_name),
        original_filename=revision.original_name,
        status=DocumentVersion.STATUS_DRAFT,
        uploaded_by=user,
        uploaded_by_name=user.get_username(),
    )
    revision.mirrored_version = mirrored
    revision.save(update_fields=["mirrored_version"])
    return mirrored


@transaction.atomic
def create_room_from_upload(*, user, title, uploaded_file):
    file_name, raw_bytes, source_format = read_uploaded_file(uploaded_file)
    room_title = room_title_from_filename(title, file_name)
    workspace = DocWorkspace.objects.create(
        name=room_workspace_name(title, file_name),
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
        source_name=file_name,
        source_format=source_format,
        source_sha256=compute_sha256(raw_bytes),
        last_activity_at=timezone.now(),
    )
    room.source_file.save(os.path.basename(file_name), ContentFile(raw_bytes), save=False)
    room.save(update_fields=["source_file"])
    revision = DocRevision.objects.create(
        room=room,
        revision_number=1,
        file=ContentFile(raw_bytes, name=file_name),
        original_name=file_name,
        file_sha256=compute_sha256(raw_bytes),
        export_format=(
            DocRevision.ExportFormat.SOURCE_HWP
            if source_format == DocRoom.SourceFormat.HWP
            else DocRevision.ExportFormat.SOURCE_HWPX
        ),
        note="원본 업로드",
        created_by=user,
    )
    try:
        _mirror_revision(room, revision, raw_bytes, user)
    except Exception:
        logger.exception("doccollab mirror failed during room creation for room=%s", room.id)
    try:
        reset_room_collab_state(room, base_revision=revision)
    except Exception:
        logger.exception("doccollab collab-state reset failed during room creation for room=%s", room.id)
    return room, revision


@transaction.atomic
def save_room_revision(*, room, user, uploaded_file, export_format, note=""):
    if export_format in {DocRevision.ExportFormat.SOURCE_HWP, DocRevision.ExportFormat.SOURCE_HWPX}:
        file_name, raw_bytes, source_format = read_uploaded_file(uploaded_file)
        expected_export_format = (
            DocRevision.ExportFormat.SOURCE_HWP
            if source_format == DocRoom.SourceFormat.HWP
            else DocRevision.ExportFormat.SOURCE_HWPX
        )
        if export_format != expected_export_format:
            raise ValidationError("원본 포맷이 올바르지 않습니다.")
    else:
        file_name = str(getattr(uploaded_file, "name", "") or "").strip() or f"{room.title}.hwp"
        raw_bytes = uploaded_file.read()
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        if not raw_bytes:
            raise ValidationError("저장할 파일이 비어 있습니다.")
        if not file_name.lower().endswith(".hwp"):
            file_name = f"{Path(file_name).stem or room.title}.hwp"
    revision = DocRevision.objects.create(
        room=room,
        revision_number=_next_revision_number(room),
        file=ContentFile(raw_bytes, name=os.path.basename(file_name)),
        original_name=os.path.basename(file_name),
        file_sha256=compute_sha256(raw_bytes),
        export_format=export_format,
        note=str(note or "").strip()[:200],
        created_by=user,
    )
    try:
        _mirror_revision(room, revision, raw_bytes, user)
    except Exception:
        logger.exception("doccollab mirror failed during revision save for room=%s revision=%s", room.id, revision.id)
    try:
        reset_room_collab_state(room, base_revision=revision)
    except Exception:
        logger.exception("doccollab collab-state reset failed during revision save for room=%s revision=%s", room.id, revision.id)
    room.last_activity_at = timezone.now()
    room.save(update_fields=["last_activity_at", "updated_at"])
    return revision


@transaction.atomic
def publish_revision(room, revision):
    room.revisions.filter(is_published=True).exclude(id=revision.id).update(is_published=False)
    revision.is_published = True
    revision.save(update_fields=["is_published"])
    room.last_activity_at = timezone.now()
    room.save(update_fields=["last_activity_at", "updated_at"])


@transaction.atomic
def create_snapshot(*, room, created_by, state_json, snapshot_kind=DocSnapshot.SnapshotKind.AUTO, revision=None):
    payload = state_json or {}
    command_count = 0
    if isinstance(payload, dict):
        command_count = len(payload.get("commands") or [])
    return DocSnapshot.objects.create(
        room=room,
        revision=revision,
        snapshot_kind=snapshot_kind,
        command_count=command_count,
        state_json=payload,
        created_by=created_by,
    )


@transaction.atomic
def record_edit_events(*, room, user, display_name, commands):
    if not commands:
        return []
    base_revision = room.revisions.order_by("-revision_number").first()
    events = []
    for command in commands:
        if not isinstance(command, dict):
            continue
        command_id = str(command.get("id") or "").strip()
        if command_id:
            existing = room.edit_events.filter(command_id=command_id).first()
            if existing is not None:
                events.append(existing)
                continue
        command_type, summary = summarize_command(command)
        event = DocEditEvent.objects.create(
            room=room,
            base_revision=base_revision,
            user=user if getattr(user, "is_authenticated", False) else None,
            command_id=command_id,
            command_type=command_type,
            display_name=str(display_name or "")[:80],
            summary=summary,
            command_json=command,
        )
        events.append(event)
    return events


def update_presence(*, room, user, session_key, display_name, role, connected):
    presence, _created = DocPresence.objects.update_or_create(
        room=room,
        session_key=session_key,
        defaults={
            "user": user if getattr(user, "is_authenticated", False) else None,
            "display_name": display_name[:80],
            "role": role,
            "is_connected": connected,
            "last_seen_at": timezone.now(),
        },
    )
    return presence


def broadcast_room_event(room, message_type, payload):
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        room_group_name(room),
        {
            "type": "doccollab.event",
            "message": {
                "type": message_type,
                "payload": payload,
                "sent_at": timezone.now().isoformat(),
            },
        },
    )


def room_payload_for_template(*, room, membership, request, editing_supported):
    worksheet = getattr(room, "worksheet", None)
    generated_draft = getattr(room, "generated_draft", None)
    is_public_library_view = bool(
        worksheet
        and membership is None
        and room.created_by_id != getattr(request.user, "id", None)
        and worksheet.is_library_published
        and worksheet.bootstrap_status == DocWorksheet.BootstrapStatus.READY
    )
    published_revision = room.revisions.filter(is_published=True).order_by("-revision_number").first()
    current_revision = published_revision if is_public_library_view else room.revisions.order_by("-revision_number").first()
    collab_state = load_room_collab_state(room)
    source_format_label = display_source_format(room.source_format)
    current_revision_format = file_format_for_revision(current_revision) if current_revision else room.source_format
    if current_revision:
        initial_file_url = reverse("doccollab:download_revision", kwargs={"room_id": room.id, "revision_id": current_revision.id})
    elif room.source_file:
        initial_file_url = reverse("doccollab:download_source", kwargs={"room_id": room.id})
    else:
        initial_file_url = ""
    source_file_url = reverse("doccollab:download_source", kwargs={"room_id": room.id}) if room.source_file else ""
    editing_enabled = getattr(membership, "role", "") in {DocMembership.Role.OWNER, DocMembership.Role.EDITOR}
    notes = f"원본 {source_format_label}는 그대로 두고, 저장본은 HWP로 남깁니다."
    if worksheet is not None:
        notes = "서버에서 만든 한 장 학습지를 바로 엽니다."
    elif generated_draft is not None or room.origin_kind == DocRoom.OriginKind.AI_DRAFT:
        notes = "AI가 만든 HWP 초안을 바로 엽니다."
    return {
        "roomId": str(room.id),
        "title": room.title,
        "membershipRole": getattr(membership, "role", ""),
        "editingEnabled": editing_enabled,
        "editingSupported": bool(editing_supported),
        "wsUrl": f"/ws/doccollab/rooms/{room.id}/" if not is_public_library_view else "",
        "initialFileUrl": initial_file_url,
        "sourceFileUrl": source_file_url,
        "saveRevisionUrl": reverse("doccollab:save_revision", kwargs={"room_id": room.id}),
        "snapshotUrl": reverse("doccollab:create_snapshot", kwargs={"room_id": room.id}),
        "studioUrl": static_url("doccollab/rhwp-studio/index.html"),
        "csrfToken": get_token(request),
        "displayName": display_name_for_user(request.user),
        "publishedRevision": serialize_revision(published_revision) if published_revision else None,
        "currentRevision": serialize_revision(current_revision) if current_revision else None,
        "sourceName": room.source_name or f"{room.title}.hwp",
        "sourceFormat": room.source_format,
        "sourceFormatLabel": source_format_label,
        "currentRevisionFormat": current_revision_format,
        "currentRevisionFormatLabel": display_source_format(current_revision_format),
        "saveFormat": DocRoom.SourceFormat.HWP,
        "saveFormatLabel": display_source_format(DocRoom.SourceFormat.HWP),
        "supportedUploadFormats": list(SUPPORTED_UPLOAD_FORMATS.values()),
        "collabState": collab_state,
        "notes": notes,
        "maxControlScan": MAX_CONTROL_SCAN,
    }
