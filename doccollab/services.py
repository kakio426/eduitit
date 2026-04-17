import hashlib
import json
import os
from pathlib import Path

from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils import timezone

from version_manager.models import Document, DocumentGroup, DocumentVersion

from .models import DocEditEvent, DocMembership, DocPresence, DocRevision, DocRoom, DocSnapshot, DocWorkspace


DOC_GROUP_NAME = "함께문서실"
MAX_SOURCE_FILE_BYTES = 20 * 1024 * 1024
MAX_CONTROL_SCAN = 12
MAX_LIVE_UPDATES = 250
SUPPORTED_UPLOAD_FORMATS = {
    ".hwp": DocRoom.SourceFormat.HWP,
    ".hwpx": DocRoom.SourceFormat.HWPX,
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
    elif command_type == "set_cell_text":
        row = int(command.get("row") or 0) + 1
        col = int(command.get("col") or 0) + 1
        text = str(command.get("text") or "").replace("\n", " ").strip()[:30]
        summary = f"표 {row},{col} 셀 수정"
        if text:
            summary = f"{summary} · {text}"
    elif command_type == "insert_table_row":
        row = int(command.get("row") or 0) + 1
        summary = f"표 {row}행 추가"
    elif command_type == "insert_table_col":
        col = int(command.get("col") or 0) + 1
        summary = f"표 {col}열 추가"
    else:
        summary = "편집"
    return command_type, summary[:200]


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
    return {
        "base_revision_id": cached.get("base_revision_id"),
        "updates": updates[-MAX_LIVE_UPDATES:],
        "updated_at": cached.get("updated_at"),
    }


def reset_room_collab_state(room, *, base_revision=None):
    payload = {
        "base_revision_id": str(base_revision.id) if getattr(base_revision, "id", None) else None,
        "updates": [],
        "updated_at": timezone.now().isoformat(),
    }
    cache.set(room_collab_state_cache_key(room), payload, timeout=60 * 60 * 12)
    return payload


def append_room_collab_update(room, update):
    payload = load_room_collab_state(room)
    updates = payload["updates"]
    updates.append(list(update or []))
    payload["updates"] = updates[-MAX_LIVE_UPDATES:]
    payload["updated_at"] = timezone.now().isoformat()
    cache.set(room_collab_state_cache_key(room), payload, timeout=60 * 60 * 12)
    return payload


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
        "export_format_label": revision.get_export_format_display(),
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
        "display_name": event.display_name,
        "summary": event.summary,
        "created_at": event.created_at.isoformat(),
    }


def serialize_edit_history(room, *, limit=20):
    return [
        serialize_edit_event(event)
        for event in room.edit_events.select_related("user").order_by("-created_at")[:limit]
    ]


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
    _mirror_revision(room, revision, raw_bytes, user)
    reset_room_collab_state(room, base_revision=revision)
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
    _mirror_revision(room, revision, raw_bytes, user)
    reset_room_collab_state(room, base_revision=revision)
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


def room_payload_for_template(*, room, membership, request):
    current_revision = room.revisions.order_by("-revision_number").first()
    collab_state = load_room_collab_state(room)
    source_format_label = display_source_format(room.source_format)
    current_revision_format = file_format_for_revision(current_revision) if current_revision else room.source_format
    return {
        "roomId": str(room.id),
        "title": room.title,
        "membershipRole": getattr(membership, "role", ""),
        "editingEnabled": getattr(membership, "role", "") in {DocMembership.Role.OWNER, DocMembership.Role.EDITOR},
        "wsUrl": f"/ws/doccollab/rooms/{room.id}/",
        "initialFileUrl": current_revision.file.url if current_revision and current_revision.file else room.source_file.url,
        "sourceFileUrl": room.source_file.url,
        "saveRevisionUrl": reverse("doccollab:save_revision", kwargs={"room_id": room.id}),
        "snapshotUrl": reverse("doccollab:create_snapshot", kwargs={"room_id": room.id}),
        "csrfToken": get_token(request),
        "displayName": display_name_for_user(request.user),
        "publishedRevision": serialize_revision(room.revisions.filter(is_published=True).order_by("-revision_number").first()) if room.revisions.exists() else None,
        "currentRevision": serialize_revision(current_revision) if current_revision else None,
        "sourceName": room.source_name,
        "sourceFormat": room.source_format,
        "sourceFormatLabel": source_format_label,
        "currentRevisionFormat": current_revision_format,
        "currentRevisionFormatLabel": display_source_format(current_revision_format),
        "saveFormat": DocRoom.SourceFormat.HWP,
        "saveFormatLabel": display_source_format(DocRoom.SourceFormat.HWP),
        "supportedUploadFormats": list(SUPPORTED_UPLOAD_FORMATS.values()),
        "collabState": collab_state,
        "notes": f"원본 {source_format_label}는 그대로 두고, 협업 저장은 HWP로 쌓습니다.",
        "maxControlScan": MAX_CONTROL_SCAN,
    }
