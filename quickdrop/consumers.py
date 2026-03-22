from http.cookies import SimpleCookie

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import QuickdropChannel
from .services import channel_snapshot_payload, load_device_cookie_value, owner_display_label, touch_device


class QuickdropConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.group_name = f"quickdrop-{self.slug}"
        channel = await self._get_channel()
        if channel is None:
            await self.close(code=4404)
            return

        access = await self._resolve_access(channel)
        if access is None:
            await self.close(code=4403)
            return

        self.channel_obj = channel
        self.is_owner = access["is_owner"]
        self.device_id = access.get("device_id")
        self.device_label = access["device_label"]

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        snapshot = await self._build_session_snapshot()
        await self.send_json(
            {
                "type": "session.snapshot",
                "payload": snapshot,
            }
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self._touch_access()
            await self.send_json({"type": "pong", "payload": {}})

    async def quickdrop_broadcast(self, event):
        await self.send_json(event["message"])

    @database_sync_to_async
    def _get_channel(self):
        return QuickdropChannel.objects.filter(slug=self.slug).first()

    @database_sync_to_async
    def _resolve_access(self, channel):
        user = self.scope.get("user")
        if getattr(user, "is_authenticated", False) and channel.owner_id == user.id:
            return {
                "is_owner": True,
                "device_id": None,
                "device_label": owner_display_label(user),
            }

        raw_cookie = self._read_cookie("quickdrop_device")
        payload = load_device_cookie_value(raw_cookie)
        if not payload or payload.get("channel_slug") != channel.slug:
            return None

        device = channel.devices.filter(
            device_id=payload.get("device_id"),
            revoked_at__isnull=True,
        ).first()
        if device is None:
            return None

        touch_device(device)
        return {
            "is_owner": False,
            "device_id": device.device_id,
            "device_label": device.label,
        }

    def _read_cookie(self, name):
        cookie_header = None
        for header_name, header_value in self.scope.get("headers", []):
            if header_name == b"cookie":
                cookie_header = header_value.decode("utf-8")
                break
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        morsel = cookie.get(name)
        return morsel.value if morsel else None

    @database_sync_to_async
    def _build_session_snapshot(self):
        return channel_snapshot_payload(self.channel_obj)

    @database_sync_to_async
    def _touch_access(self):
        if self.is_owner or not self.device_id:
            return
        device = self.channel_obj.devices.filter(device_id=self.device_id, revoked_at__isnull=True).first()
        if device:
            touch_device(device)
