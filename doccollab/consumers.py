from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import DocEditEvent, DocMembership
from .services import (
    append_room_command_batch,
    display_name_for_user,
    get_room_for_user,
    record_edit_events,
    room_group_name,
    serialize_edit_event,
    serialize_revision,
    serialize_presence_list,
    serialize_room,
    update_presence,
)


class DoccollabRoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        room, membership = await self._resolve_room(user)
        if room is None:
            await self.close(code=4404)
            return
        if membership is None:
            await self.close(code=4403)
            return
        self.room = room
        self.membership = membership
        self.group_name = room_group_name(room)
        self.session_key = self.channel_name
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._touch_presence(True)
        await self.send_json(
            {
                "type": "room.snapshot",
                "payload": {
                    **(await self._build_snapshot()),
                    "session_key": self.session_key,
                },
            }
        )
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "doccollab.event",
                "message": {
                    "type": "presence.join",
                    "payload": {"participants": await self._presence_payload()},
                },
            },
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, "room"):
            await self._touch_presence(False)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "doccollab.event",
                    "message": {
                        "type": "presence.leave",
                        "payload": {"participants": await self._presence_payload()},
                    },
                },
            )

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")
        if event_type == "ping":
            await self._touch_presence(True)
            await self.send_json({"type": "pong", "payload": {}})
            return
        if event_type == "editor.command":
            if self.membership.role not in {DocMembership.Role.OWNER, DocMembership.Role.EDITOR}:
                await self.send_json({"type": "error", "payload": {"message": "editor only"}})
                return
            await self._touch_presence(True)
            payload = content.get("payload", {}) or {}
            commands = payload.get("commands") or []
            state, accepted, reason = await self._append_command_batch(
                {
                    "batchId": payload.get("batchId"),
                    "baseRevisionId": payload.get("baseRevisionId"),
                    "senderSessionKey": payload.get("senderSessionKey") or self.session_key,
                    "commands": commands,
                    "selection": payload.get("selection") or {},
                }
            )
            if not accepted:
                if reason == "duplicate batchId":
                    return
                await self.send_json({"type": "error", "payload": {"message": reason or "invalid command batch"}})
                return
            edit_events = await self._record_edit_events(commands)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "doccollab.event",
                    "message": {
                        "type": "editor.command",
                        "payload": {
                            "batchId": payload.get("batchId"),
                            "baseRevisionId": payload.get("baseRevisionId") or state.get("base_revision_id"),
                            "senderSessionKey": payload.get("senderSessionKey") or self.session_key,
                            "sender": display_name_for_user(self.scope.get("user")),
                            "commands": commands,
                            "selection": payload.get("selection") or {},
                            "edit_events": edit_events,
                        },
                    },
                },
            )
            return
        if event_type == "editor.selection":
            await self._touch_presence(True)
            payload = content.get("payload", {}) or {}
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "doccollab.event",
                    "message": {
                        "type": "editor.selection",
                        "payload": {
                            "senderSessionKey": payload.get("senderSessionKey") or self.session_key,
                            "sender": display_name_for_user(self.scope.get("user")),
                            "selection": payload.get("selection") or {},
                        },
                    },
                },
            )
            return
        if event_type == "revision.saved":
            if self.membership.role not in {DocMembership.Role.OWNER, DocMembership.Role.EDITOR}:
                await self.send_json({"type": "error", "payload": {"message": "editor only"}})
                return
            await self._touch_presence(True)
            payload = content.get("payload", {}) or {}
            revision_payload = await self._revision_payload(
                payload.get("revisionId"),
                payload.get("editEvents"),
            )
            if revision_payload is None:
                await self.send_json({"type": "error", "payload": {"message": "invalid revision"}})
                return
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "doccollab.event",
                    "message": {
                        "type": "revision.saved",
                        "payload": revision_payload,
                    },
                },
            )
            return
        await self.send_json({"type": "error", "payload": {"message": "unsupported event"}})

    async def doccollab_event(self, event):
        await self.send_json(event["message"])

    @database_sync_to_async
    def _resolve_room(self, user):
        return get_room_for_user(self.room_id, user)

    @database_sync_to_async
    def _build_snapshot(self):
        fresh_room, fresh_membership = get_room_for_user(self.room_id, self.scope.get("user"))
        return serialize_room(fresh_room, membership=fresh_membership)

    @database_sync_to_async
    def _presence_payload(self):
        fresh_room, _membership = get_room_for_user(self.room_id, self.scope.get("user"))
        return serialize_presence_list(fresh_room)

    @database_sync_to_async
    def _touch_presence(self, connected):
        update_presence(
            room=self.room,
            user=self.scope.get("user"),
            session_key=self.session_key,
            display_name=display_name_for_user(self.scope.get("user")),
            role=self.membership.role,
            connected=connected,
        )

    @database_sync_to_async
    def _append_command_batch(self, batch):
        return append_room_command_batch(self.room, batch)

    @database_sync_to_async
    def _record_edit_events(self, commands):
        events = record_edit_events(
            room=self.room,
            user=self.scope.get("user"),
            display_name=display_name_for_user(self.scope.get("user")),
            commands=commands,
        )
        return [serialize_edit_event(event) for event in events]

    @database_sync_to_async
    def _revision_payload(self, revision_id, fallback_edit_events=None):
        if not revision_id:
            return None
        revision = self.room.revisions.filter(id=revision_id).first()
        if revision is None:
            return None
        edit_events = [
            serialize_edit_event(event)
            for event in DocEditEvent.objects.filter(room=self.room, command_id=f"save:{revision.id}").order_by("-created_at")
        ]
        if not edit_events and isinstance(fallback_edit_events, list):
            edit_events = [item for item in fallback_edit_events if isinstance(item, dict)]
        return {
            "revision": serialize_revision(revision),
            "edit_events": edit_events,
        }
