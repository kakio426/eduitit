import asyncio
from contextlib import suppress

from channels.testing.websocket import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase

from config.asgi import application
from doccollab.models import DocEditEvent, DocMembership
from doccollab.services import create_room_from_upload, save_room_revision, serialize_edit_event


User = get_user_model()


def hwpx_upload(name="room.hwpx", content=b"consumer hwpx bytes"):
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


class DoccollabConsumerTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.owner = User.objects.create_user(
            username="doc-owner-ws",
            email="doc-owner-ws@example.com",
            password="pw123456",
        )
        self.editor = User.objects.create_user(
            username="doc-editor-ws",
            email="doc-editor-ws@example.com",
            password="pw123456",
        )
        self.viewer = User.objects.create_user(
            username="doc-viewer-ws",
            email="doc-viewer-ws@example.com",
            password="pw123456",
        )
        self.room, self.initial_revision = create_room_from_upload(
            user=self.owner,
            title="웹소켓 문서",
            uploaded_file=hwpx_upload(),
        )
        DocMembership.objects.create(
            workspace=self.room.workspace,
            user=self.editor,
            role=DocMembership.Role.EDITOR,
            status=DocMembership.Status.ACTIVE,
            invited_by=self.owner,
        )
        DocMembership.objects.create(
            workspace=self.room.workspace,
            user=self.viewer,
            role=DocMembership.Role.VIEWER,
            status=DocMembership.Status.ACTIVE,
            invited_by=self.owner,
        )
        self.owner_cookie = self._build_session_cookie(self.owner)
        self.editor_cookie = self._build_session_cookie(self.editor)
        self.viewer_cookie = self._build_session_cookie(self.viewer)

    def _build_session_cookie(self, user):
        store = SessionStore()
        store[SESSION_KEY] = str(user.pk)
        store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
        store[HASH_SESSION_KEY] = user.get_session_auth_hash()
        store.save()
        return f"{settings.SESSION_COOKIE_NAME}={store.session_key}"

    def _headers(self, cookie_value):
        return [
            (b"cookie", cookie_value.encode("utf-8")),
            (b"host", b"testserver"),
            (b"origin", b"http://testserver"),
        ]

    async def _connect(self, cookie_value):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/doccollab/rooms/{self.room.id}/",
            headers=self._headers(cookie_value),
        )
        connected, detail = await communicator.connect()
        self.assertTrue(connected, detail)
        return communicator

    async def _drain(self, *communicators):
        for communicator in communicators:
            while not await communicator.receive_nothing(timeout=0.05, interval=0.01):
                await communicator.receive_json_from()

    async def _disconnect(self, communicator):
        with suppress(asyncio.CancelledError):
            await communicator.disconnect()

    def test_snapshot_contains_cached_updates_and_editor_command_broadcasts(self):
        async def runner():
            owner = await self._connect(self.owner_cookie)
            first_message = await owner.receive_json_from(timeout=1)
            self.assertEqual(first_message["type"], "room.snapshot")
            self.assertTrue(first_message["payload"]["session_key"])
            base_revision_id = first_message["payload"]["collab_state"]["base_revision_id"]
            await self._drain(owner)

            await owner.send_json_to(
                {
                    "type": "editor.command",
                    "payload": {
                        "batchId": "batch-1",
                        "baseRevisionId": base_revision_id,
                        "senderSessionKey": "owner-session",
                        "selection": {"cursor": {"paragraphIndex": 0, "charOffset": 3}},
                        "commands": [{"id": "cmd-1", "type": "insert_text", "text": "첫 문장"}],
                    },
                }
            )
            echoed_to_owner = await owner.receive_json_from(timeout=1)
            self.assertEqual(echoed_to_owner["type"], "editor.command")
            self.assertEqual(echoed_to_owner["payload"]["batchId"], "batch-1")
            self.assertEqual(echoed_to_owner["payload"]["baseRevisionId"], base_revision_id)
            self.assertEqual(echoed_to_owner["payload"]["senderSessionKey"], "owner-session")
            self.assertEqual(echoed_to_owner["payload"]["commands"][0]["type"], "insert_text")
            self.assertEqual(echoed_to_owner["payload"]["edit_events"][0]["summary"], "문장 입력 · 첫 문장")

            editor = await self._connect(self.editor_cookie)
            snapshot = await editor.receive_json_from(timeout=1)
            self.assertEqual(snapshot["type"], "room.snapshot")
            self.assertEqual(snapshot["payload"]["collab_state"]["updates"][0]["batchId"], "batch-1")
            self.assertEqual(snapshot["payload"]["collab_state"]["updates"][0]["commands"][0]["type"], "insert_text")
            self.assertEqual(snapshot["payload"]["edit_history"][0]["summary"], "문장 입력 · 첫 문장")
            await self._drain(owner, editor)

            await owner.send_json_to(
                {
                    "type": "editor.command",
                    "payload": {
                        "batchId": "batch-2",
                        "baseRevisionId": base_revision_id,
                        "senderSessionKey": "owner-session",
                        "commands": [{"id": "cmd-2", "type": "split_paragraph"}],
                    },
                }
            )
            echoed = await editor.receive_json_from(timeout=1)
            self.assertEqual(echoed["type"], "editor.command")
            self.assertEqual(echoed["payload"]["batchId"], "batch-2")
            self.assertEqual(echoed["payload"]["commands"][0]["type"], "split_paragraph")
            self.assertEqual(echoed["payload"]["edit_events"][0]["summary"], "새 문단")

            await self._disconnect(owner)
            await self._disconnect(editor)

        asyncio.run(runner())
        self.assertEqual(DocEditEvent.objects.filter(room=self.room).count(), 2)
        self.assertTrue(DocEditEvent.objects.filter(room=self.room, command_id="cmd-1", summary="문장 입력 · 첫 문장").exists())

    def test_viewer_cannot_send_editor_command(self):
        async def runner():
            viewer = await self._connect(self.viewer_cookie)
            first_message = await viewer.receive_json_from(timeout=1)
            self.assertEqual(first_message["type"], "room.snapshot")
            await self._drain(viewer)

            await viewer.send_json_to(
                {
                    "type": "editor.command",
                    "payload": {
                        "batchId": "viewer-batch",
                        "baseRevisionId": first_message["payload"]["collab_state"]["base_revision_id"],
                        "commands": [{"id": "viewer-cmd", "type": "insert_text", "text": "차단"}],
                    },
                }
            )
            error = await viewer.receive_json_from(timeout=1)
            self.assertEqual(error["type"], "error")
            self.assertEqual(error["payload"]["message"], "editor only")

            await self._disconnect(viewer)

        asyncio.run(runner())

    def test_duplicate_batch_is_ignored_after_first_accept(self):
        async def runner():
            owner = await self._connect(self.owner_cookie)
            snapshot = await owner.receive_json_from(timeout=1)
            self.assertEqual(snapshot["type"], "room.snapshot")
            base_revision_id = snapshot["payload"]["collab_state"]["base_revision_id"]
            await self._drain(owner)

            payload = {
                "type": "editor.command",
                "payload": {
                    "batchId": "dup-batch",
                    "baseRevisionId": base_revision_id,
                    "senderSessionKey": "owner-session",
                    "commands": [{"id": "dup-cmd", "type": "insert_text", "text": "중복 방지"}],
                },
            }

            await owner.send_json_to(payload)
            first_echo = await owner.receive_json_from(timeout=1)
            self.assertEqual(first_echo["type"], "editor.command")
            self.assertEqual(first_echo["payload"]["batchId"], "dup-batch")

            await owner.send_json_to(payload)
            self.assertTrue(await owner.receive_nothing(timeout=0.2, interval=0.05))

            await self._disconnect(owner)

        asyncio.run(runner())
        self.assertEqual(DocEditEvent.objects.filter(room=self.room, command_id="dup-cmd").count(), 1)

    def test_stale_base_revision_is_rejected_after_save_resets_live_base(self):
        latest_revision = save_room_revision(
            room=self.room,
            user=self.owner,
            uploaded_file=hwpx_upload("saved-after-collab.hwp", content=b"saved hwp bytes"),
            export_format="hwp_export",
            note="새 저장본",
        )

        async def runner():
            owner = await self._connect(self.owner_cookie)
            snapshot = await owner.receive_json_from(timeout=1)
            self.assertEqual(snapshot["type"], "room.snapshot")
            self.assertEqual(snapshot["payload"]["collab_state"]["base_revision_id"], str(latest_revision.id))
            await self._drain(owner)

            await owner.send_json_to(
                {
                    "type": "editor.command",
                    "payload": {
                        "batchId": "stale-batch",
                        "baseRevisionId": str(self.initial_revision.id),
                        "senderSessionKey": "owner-session",
                        "commands": [{"id": "stale-cmd", "type": "insert_text", "text": "오래된 기준"}],
                    },
                }
            )
            error = await owner.receive_json_from(timeout=1)
            self.assertEqual(error["type"], "error")
            self.assertEqual(error["payload"]["message"], "stale base revision")

            await self._disconnect(owner)

        asyncio.run(runner())
        self.assertFalse(DocEditEvent.objects.filter(room=self.room, command_id="stale-cmd").exists())

    def test_revision_saved_event_is_relayed_to_other_tabs(self):
        latest_revision = save_room_revision(
            room=self.room,
            user=self.owner,
            uploaded_file=hwpx_upload("saved-after-collab.hwp", content=b"saved hwp bytes"),
            export_format="hwp_export",
            note="새 저장본",
        )
        save_event = DocEditEvent.objects.create(
            room=self.room,
            user=self.owner,
            display_name="doc-owner-ws",
            command_id=f"save:{latest_revision.id}",
            command_type="save_revision",
            summary=f"저장본 저장 · r{latest_revision.revision_number}",
        )

        async def runner():
            owner = await self._connect(self.owner_cookie)
            owner_snapshot = await owner.receive_json_from(timeout=1)
            self.assertEqual(owner_snapshot["type"], "room.snapshot")

            editor = await self._connect(self.editor_cookie)
            editor_snapshot = await editor.receive_json_from(timeout=1)
            self.assertEqual(editor_snapshot["type"], "room.snapshot")
            await self._drain(owner, editor)

            await owner.send_json_to(
                {
                    "type": "revision.saved",
                    "payload": {
                        "revisionId": str(latest_revision.id),
                        "editEvents": [serialize_edit_event(save_event)],
                    },
                }
            )

            owner_echo = await owner.receive_json_from(timeout=1)
            editor_echo = await editor.receive_json_from(timeout=1)

            self.assertEqual(owner_echo["type"], "revision.saved")
            self.assertEqual(editor_echo["type"], "revision.saved")
            self.assertEqual(owner_echo["payload"]["revision"]["id"], str(latest_revision.id))
            self.assertEqual(editor_echo["payload"]["revision"]["id"], str(latest_revision.id))
            self.assertEqual(editor_echo["payload"]["revision"]["export_format"], "hwp_export")
            self.assertEqual(editor_echo["payload"]["edit_events"][0]["summary"], f"저장본 저장 · r{latest_revision.revision_number}")

            await self._disconnect(owner)
            await self._disconnect(editor)

        asyncio.run(runner())
