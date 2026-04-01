from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import DatabaseError

from .services import (
    build_notification_summary,
    get_room_for_user,
    user_group_name,
    workspace_group_name,
)


class SchoolcommRoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        try:
            room, membership = await self._get_room_and_membership()
        except DatabaseError:
            await self.close(code=1013)
            return
        if room is None:
            await self.close(code=4404)
            return
        if membership is None:
            await self.close(code=4403)
            return
        self.room = room
        self.membership = membership
        self.group_name = workspace_group_name(room)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "room.snapshot",
                "payload": {
                    "room_id": str(room.id),
                },
            }
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong", "payload": {}})

    async def schoolcomm_event(self, event):
        await self.send_json(event["message"])

    @database_sync_to_async
    def _get_room_and_membership(self):
        user = self.scope.get("user")
        room_id = self.scope["url_route"]["kwargs"]["room_id"]
        return get_room_for_user(room_id, user)


class SchoolcommUserConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return
        self.user = user
        self.group_name = user_group_name(user)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        try:
            summary = await self._build_summary()
        except DatabaseError:
            await self.close(code=1013)
            return
        await self.send_json({"type": "notification.summary", "payload": summary})

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            try:
                summary = await self._build_summary()
            except DatabaseError:
                await self.close(code=1013)
                return
            await self.send_json({"type": "notification.summary", "payload": summary})

    async def schoolcomm_event(self, event):
        await self.send_json(event["message"])

    @database_sync_to_async
    def _build_summary(self):
        return build_notification_summary(self.user)
