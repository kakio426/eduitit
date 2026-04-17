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
from doccollab.services import create_room_from_upload


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
        self.room, _revision = create_room_from_upload(
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
            await self._drain(owner)

            await owner.send_json_to(
                {
                    "type": "editor.command",
                    "payload": {
                        "update": [1, 2, 3],
                        "commands": [{"id": "cmd-1", "type": "insert_text", "text": "첫 문장"}],
                    },
                }
            )
            echoed_to_owner = await owner.receive_json_from(timeout=1)
            self.assertEqual(echoed_to_owner["type"], "editor.command")
            self.assertEqual(echoed_to_owner["payload"]["edit_events"][0]["summary"], "문장 입력 · 첫 문장")

            editor = await self._connect(self.editor_cookie)
            snapshot = await editor.receive_json_from(timeout=1)
            self.assertEqual(snapshot["type"], "room.snapshot")
            self.assertIn([1, 2, 3], snapshot["payload"]["collab_state"]["updates"])
            self.assertEqual(snapshot["payload"]["edit_history"][0]["summary"], "문장 입력 · 첫 문장")
            await self._drain(owner, editor)

            await owner.send_json_to(
                {
                    "type": "editor.command",
                    "payload": {
                        "update": [4, 5, 6],
                        "commands": [{"id": "cmd-2", "type": "split_paragraph"}],
                    },
                }
            )
            echoed = await editor.receive_json_from(timeout=1)
            self.assertEqual(echoed["type"], "editor.command")
            self.assertEqual(echoed["payload"]["update"], [4, 5, 6])
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

            await viewer.send_json_to({"type": "editor.command", "payload": {"update": [9, 9, 9]}})
            error = await viewer.receive_json_from(timeout=1)
            self.assertEqual(error["type"], "error")
            self.assertEqual(error["payload"]["message"], "editor only")

            await self._disconnect(viewer)

        asyncio.run(runner())
