import asyncio
from contextlib import suppress

from asgiref.sync import sync_to_async
from channels.testing.websocket import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from config.asgi import application
from core.models import UserProfile
from quickdrop.models import QuickdropDevice
from quickdrop.services import (
    DEVICE_COOKIE_NAME,
    build_device_cookie_value,
    broadcast_item_replace,
    broadcast_session_ended,
    end_session,
    ensure_live_session,
    get_or_create_personal_channel,
    replace_with_text,
)


User = get_user_model()


class QuickdropConsumerTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = User.objects.create_user(
            username="quickdrop_ws",
            email="quickdrop_ws@example.com",
            password="pw123456",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "웹소켓쌤"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.channel = get_or_create_personal_channel(self.user)
        self.device = QuickdropDevice.objects.create(
            channel=self.channel,
            device_id="device-ws-1",
            label="iPhone",
            user_agent_summary="iPhone",
        )
        self.cookie_value = build_device_cookie_value(self.channel, self.device)

    def _headers(self):
        return [
            (b"cookie", f"{DEVICE_COOKIE_NAME}={self.cookie_value}".encode("utf-8")),
            (b"host", b"testserver"),
            (b"origin", b"http://testserver"),
        ]

    async def _disconnect(self, communicator):
        with suppress(asyncio.CancelledError):
            await communicator.disconnect()

    def test_device_receives_initial_snapshot(self):
        async def runner():
            communicator = WebsocketCommunicator(
                application,
                f"/quickdrop/ws/{self.channel.slug}/",
                headers=self._headers(),
            )
            connected, _detail = await communicator.connect()
            self.assertTrue(connected)
            snapshot = await communicator.receive_json_from(timeout=1)
            self.assertEqual(snapshot["type"], "session.snapshot")
            self.assertEqual(snapshot["payload"]["current_kind"], "empty")
            await self._disconnect(communicator)

        asyncio.run(runner())

    def test_item_replace_broadcast_reaches_connected_device(self):
        async def runner():
            communicator = WebsocketCommunicator(
                application,
                f"/quickdrop/ws/{self.channel.slug}/",
                headers=self._headers(),
            )
            connected, _detail = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_json_from(timeout=1)

            session = await sync_to_async(lambda: ensure_live_session(self.channel)[0])()
            session = await sync_to_async(replace_with_text)(session, "웹소켓 텍스트")
            await sync_to_async(broadcast_item_replace)(session)

            message = await communicator.receive_json_from(timeout=1)
            self.assertEqual(message["type"], "item.replace")
            self.assertEqual(message["payload"]["current_text"], "웹소켓 텍스트")
            await self._disconnect(communicator)

        asyncio.run(runner())

    def test_ended_session_is_broadcast(self):
        async def runner():
            communicator = WebsocketCommunicator(
                application,
                f"/quickdrop/ws/{self.channel.slug}/",
                headers=self._headers(),
            )
            connected, _detail = await communicator.connect()
            self.assertTrue(connected)
            await communicator.receive_json_from(timeout=1)

            session = await sync_to_async(lambda: ensure_live_session(self.channel)[0])()
            session = await sync_to_async(replace_with_text)(session, "끝날 내용")
            await sync_to_async(end_session)(session)
            await sync_to_async(lambda: broadcast_session_ended(session))()

            message = await communicator.receive_json_from(timeout=1)
            self.assertEqual(message["type"], "session.ended")
            self.assertEqual(message["payload"]["status"], "ended")
            self.assertEqual(message["payload"]["current_kind"], "empty")
            await self._disconnect(communicator)

        asyncio.run(runner())
