from http.cookies import SimpleCookie
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from .models import TextbookLiveEvent, TextbookLivePageState, TextbookLiveParticipant, TextbookLiveSession
from .services import ALLOWED_WS_EVENTS, NON_PERSISTED_EVENTS, TEACHER_ONLY_EVENTS, load_access_cookie_value


class TextbookLiveConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"textbooks-live-{self.session_id}"
        self.query = parse_qs((self.scope.get("query_string") or b"").decode("utf-8"))

        session = await self._get_session()
        if session is None:
            await self.close(code=4404)
            return

        access = await self._resolve_access(session)
        if access is None:
            await self.close(code=4403)
            return

        self.session_role = access["role"]
        self.device_id = access["device_id"]
        self.display_name = access["display_name"]
        self.viewer_user_id = access.get("user_id")

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        participants = await self._touch_participant(connected=True)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "live.broadcast",
                "message": {
                    "type": "presence.join",
                    "seq": session.last_seq,
                    "actor": self.session_role,
                    "payload": {"participants": participants},
                    "sent_at": timezone.now().isoformat(),
                },
            },
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, "device_id"):
            participants = await self._touch_participant(connected=False)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "live.broadcast",
                    "message": {
                        "type": "presence.leave",
                        "seq": await self._current_seq(),
                        "actor": self.session_role,
                        "payload": {"participants": participants},
                        "sent_at": timezone.now().isoformat(),
                    },
                },
            )

    async def receive_json(self, content, **kwargs):
        event_type = content.get("type")
        if event_type not in ALLOWED_WS_EVENTS:
            await self.send_json({"type": "error", "payload": {"message": "unsupported event"}})
            return

        if self.session_role != TextbookLiveParticipant.ROLE_TEACHER and event_type in TEACHER_ONLY_EVENTS:
            await self.send_json({"type": "error", "payload": {"message": "teacher only"}})
            return

        seq = int(content.get("seq") or 0)
        payload = content.get("payload") or {}
        page_index = payload.get("page_index")
        if page_index is None:
            page_index = content.get("page_index")
        actor = self.session_role
        envelope = {
            "type": event_type,
            "seq": seq,
            "actor": actor,
            "payload": payload,
            "sent_at": timezone.now().isoformat(),
        }

        if event_type in {"presence.join", "presence.leave"}:
            participants = await self._touch_participant(connected=event_type == "presence.join")
            envelope["payload"] = {"participants": participants}
            await self.channel_layer.group_send(self.group_name, {"type": "live.broadcast", "message": envelope})
            return

        accepted = await self._apply_event(envelope, page_index)
        if not accepted:
            return
        await self.channel_layer.group_send(self.group_name, {"type": "live.broadcast", "message": envelope})

    async def live_broadcast(self, event):
        await self.send_json(event["message"])

    @database_sync_to_async
    def _get_session(self):
        return (
            TextbookLiveSession.objects.select_related("teacher", "material")
            .filter(id=self.session_id)
            .first()
        )

    async def _resolve_access(self, session):
        user = self.scope.get("user")
        requested_role = (self.query.get("role") or [TextbookLiveParticipant.ROLE_STUDENT])[0]
        requested_device_id = (self.query.get("device_id") or [None])[0]

        if getattr(user, "is_authenticated", False) and user.id == session.teacher_id:
            role = requested_role if requested_role in {
                TextbookLiveParticipant.ROLE_TEACHER,
                TextbookLiveParticipant.ROLE_DISPLAY,
            } else TextbookLiveParticipant.ROLE_TEACHER
            return {
                "role": role,
                "device_id": requested_device_id or f"{role}-{user.id}",
                "display_name": "TV 화면" if role == TextbookLiveParticipant.ROLE_DISPLAY else user.get_username(),
                "user_id": user.id,
            }

        raw_cookie = self._read_cookie("textbooks_live_access")
        payload = load_access_cookie_value(raw_cookie)
        if not payload or payload.get("session_id") != str(session.id):
            return None
        return {
            "role": TextbookLiveParticipant.ROLE_STUDENT,
            "device_id": payload.get("device_id") or requested_device_id,
            "display_name": payload.get("display_name") or "학생",
            "user_id": None,
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
    def _touch_participant(self, connected):
        session = TextbookLiveSession.objects.get(id=self.session_id)
        defaults = {
            "role": self.session_role,
            "display_name": self.display_name,
            "user_id": self.viewer_user_id,
            "is_connected": connected,
        }
        participant, _ = TextbookLiveParticipant.objects.get_or_create(
            session=session,
            device_id=self.device_id,
            defaults=defaults,
        )
        participant.role = self.session_role
        participant.display_name = self.display_name
        participant.user_id = self.viewer_user_id
        participant.is_connected = connected
        participant.last_seen_at = timezone.now()
        participant.save(update_fields=["role", "display_name", "user", "is_connected", "last_seen_at"])
        session.last_heartbeat = timezone.now()
        session.save(update_fields=["last_heartbeat", "updated_at"])
        return [
            {
                "id": item.device_id,
                "role": item.role,
                "display_name": item.display_name,
                "is_connected": item.is_connected,
                "last_seen_at": item.last_seen_at.isoformat(),
            }
            for item in session.participants.order_by("role", "display_name")
        ]

    @database_sync_to_async
    def _apply_event(self, envelope, page_index):
        session = TextbookLiveSession.objects.get(id=self.session_id)
        event_type = envelope["type"]
        seq = envelope["seq"]
        payload = envelope["payload"] or {}

        if event_type not in NON_PERSISTED_EVENTS and seq <= session.last_seq:
            return False

        if event_type == "session.navigate":
            next_page = max(1, int(payload.get("current_page") or session.current_page))
            if session.material.page_count:
                next_page = min(next_page, session.material.page_count)
            session.current_page = next_page
            session.zoom_scale = float(payload.get("zoom_scale") or session.zoom_scale or 1.0)
        elif event_type == "session.follow":
            session.follow_mode = bool(payload.get("follow_mode"))
            if payload.get("current_page"):
                next_page = max(1, int(payload.get("current_page") or session.current_page))
                if session.material.page_count:
                    next_page = min(next_page, session.material.page_count)
                session.current_page = next_page
            if payload.get("zoom_scale"):
                session.zoom_scale = float(payload.get("zoom_scale") or session.zoom_scale or 1.0)
        elif event_type == "session.snapshot":
            if payload.get("current_page"):
                session.current_page = max(1, int(payload["current_page"]))
            if payload.get("zoom_scale"):
                session.zoom_scale = float(payload["zoom_scale"])
            viewport = dict(session.viewport_json or {})
            viewport.update(payload.get("viewport") or {})
            session.viewport_json = viewport
        elif event_type in {"annotation.upsert", "annotation.delete"}:
            if not page_index:
                return False
            state, _ = TextbookLivePageState.objects.get_or_create(
                session=session,
                page_index=int(page_index),
                defaults={"revision": 0, "fabric_json": {}},
            )
            state.fabric_json = payload.get("fabric_json") or {}
            state.revision += 1
            state.save(update_fields=["fabric_json", "revision", "updated_at"])
            envelope["payload"] = {**payload, "revision": state.revision, "page_index": int(page_index)}
        elif event_type == "session.end":
            session.status = TextbookLiveSession.STATUS_ENDED
            session.ended_at = timezone.now()

        session.last_heartbeat = timezone.now()
        if event_type not in NON_PERSISTED_EVENTS:
            session.last_seq = seq
        session.save(update_fields=[
            "current_page",
            "zoom_scale",
            "follow_mode",
            "viewport_json",
            "status",
            "ended_at",
            "last_heartbeat",
            "last_seq",
            "updated_at",
        ])

        if event_type not in NON_PERSISTED_EVENTS:
            TextbookLiveEvent.objects.create(
                session=session,
                seq=seq,
                event_type=event_type,
                page_index=int(page_index) if page_index else None,
                payload_json=envelope["payload"],
                actor_role=self.session_role,
            )
        return True

    @database_sync_to_async
    def _current_seq(self):
        return TextbookLiveSession.objects.filter(id=self.session_id).values_list("last_seq", flat=True).first() or 0
