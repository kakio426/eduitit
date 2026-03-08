import asyncio
from contextlib import suppress

from channels.testing.websocket import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import TransactionTestCase
from django.utils import timezone

from config.asgi import application
from happy_seed.models import HSClassroom
from textbooks.models import TextbookLiveSession, TextbookMaterial
from textbooks.services import ACCESS_COOKIE_NAME, build_access_cookie_value


User = get_user_model()


class TextbookConsumerTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher_ws",
            email="teacher-ws@example.com",
            password="pw123456",
        )
        self.teacher.userprofile.nickname = "라이브교사"
        self.teacher.userprofile.save(update_fields=["nickname"])
        self.classroom = HSClassroom.objects.create(teacher=self.teacher, name="6학년 1반")
        self.material = TextbookMaterial.objects.create(
            teacher=self.teacher,
            subject="SCIENCE",
            grade="6학년 1학기",
            unit_title="식물의 구조",
            title="식물 PDF",
            source_type=TextbookMaterial.SOURCE_PDF,
            page_count=5,
            pdf_sha256="abc123",
            original_filename="plants.pdf",
            is_published=True,
        )
        self.session = TextbookLiveSession.objects.create(
            material=self.material,
            teacher=self.teacher,
            classroom=self.classroom,
            status=TextbookLiveSession.STATUS_LIVE,
            join_code="123456",
            current_page=1,
            zoom_scale=1.0,
            viewport_json={},
            started_at=timezone.now(),
            last_heartbeat=timezone.now(),
        )
        self.teacher_cookie = self._build_session_cookie(self.teacher)
        self.student_cookie = self._build_student_cookie()

    def _build_session_cookie(self, user):
        store = SessionStore()
        store[SESSION_KEY] = str(user.pk)
        store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
        store[HASH_SESSION_KEY] = user.get_session_auth_hash()
        store.save()
        return f"{settings.SESSION_COOKIE_NAME}={store.session_key}"

    def _build_student_cookie(self, name="학생1"):
        value = build_access_cookie_value(
            session=self.session,
            role="student",
            device_id="student-device-1",
            display_name=name,
        )
        return f"{ACCESS_COOKIE_NAME}={value}"

    def _ws_headers(self, cookie_value):
        return [
            (b"cookie", cookie_value.encode("utf-8")),
            (b"host", b"testserver"),
            (b"origin", b"http://testserver"),
        ]

    async def _connect_teacher(self):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/textbooks/live/{self.session.id}/?role=teacher&device_id=teacher-device-1",
            headers=self._ws_headers(self.teacher_cookie),
        )
        connected, detail = await communicator.connect()
        self.assertTrue(connected, detail)
        return communicator

    async def _connect_student(self):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/textbooks/live/{self.session.id}/?role=student&device_id=student-device-1",
            headers=self._ws_headers(self.student_cookie),
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

    def test_student_cannot_send_mutating_event(self):
        async def runner():
            student = await self._connect_student()
            await self._drain(student)
            await student.send_json_to({
                "type": "annotation.upsert",
                "seq": 1,
                "payload": {"page_index": 1, "fabric_json": {"objects": []}},
            })
            message = await student.receive_json_from(timeout=1)
            self.assertEqual(message["type"], "error")
            await self._disconnect(student)

        asyncio.run(runner())

    def test_teacher_navigation_broadcasts_to_student(self):
        async def runner():
            teacher = await self._connect_teacher()
            student = await self._connect_student()
            await self._drain(teacher, student)
            await teacher.send_json_to({
                "type": "session.navigate",
                "seq": 1,
                "payload": {"current_page": 3, "zoom_scale": 1.0},
            })
            received = await student.receive_json_from(timeout=1)
            self.assertEqual(received["type"], "session.navigate")
            self.assertEqual(received["payload"]["current_page"], 3)
            await self._disconnect(teacher)
            await self._disconnect(student)

        asyncio.run(runner())
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_page, 3)


    def test_follow_mode_relocks_students_to_teacher_page(self):
        async def runner():
            teacher = await self._connect_teacher()
            student = await self._connect_student()
            await self._drain(teacher, student)
            await teacher.send_json_to({
                "type": "session.follow",
                "seq": 1,
                "payload": {"follow_mode": True, "current_page": 4, "zoom_scale": 1.25},
            })
            received = await student.receive_json_from(timeout=1)
            self.assertEqual(received["type"], "session.follow")
            self.assertTrue(received["payload"]["follow_mode"])
            self.assertEqual(received["payload"]["current_page"], 4)
            self.assertEqual(received["payload"]["zoom_scale"], 1.25)
            await self._disconnect(teacher)
            await self._disconnect(student)

        asyncio.run(runner())
        self.session.refresh_from_db()
        self.assertTrue(self.session.follow_mode)
        self.assertEqual(self.session.current_page, 4)
        self.assertEqual(self.session.zoom_scale, 1.25)

    def test_stale_seq_is_ignored(self):
        async def runner():
            teacher = await self._connect_teacher()
            await self._drain(teacher)
            await teacher.send_json_to({
                "type": "session.navigate",
                "seq": 2,
                "payload": {"current_page": 4, "zoom_scale": 1.0},
            })
            await teacher.receive_json_from(timeout=1)
            await teacher.send_json_to({
                "type": "session.navigate",
                "seq": 1,
                "payload": {"current_page": 2, "zoom_scale": 1.0},
            })
            await asyncio.sleep(0.2)
            await self._disconnect(teacher)

        asyncio.run(runner())
        self.session.refresh_from_db()
        self.assertEqual(self.session.current_page, 4)
