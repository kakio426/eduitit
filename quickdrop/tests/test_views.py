from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.context_processors import search_products
from core.models import UserProfile
from products.models import Product
from quickdrop.models import QuickdropDevice, QuickdropItem, QuickdropSession
from quickdrop.services import (
    DEVICE_COOKIE_NAME,
    DEVICE_COOKIE_PATH,
    build_device_cookie_value,
    build_pair_token,
    get_or_create_personal_channel,
)


User = get_user_model()

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc````\x00"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class QuickdropViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="quickdrop_teacher",
            email="quickdrop_teacher@example.com",
            password="pw123456",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "빠른쌤"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.channel = get_or_create_personal_channel(self.user)
        self.client.force_login(self.user)

    def _pair_device_cookie(self, label="iPhone"):
        device = QuickdropDevice.objects.create(
            channel=self.channel,
            device_id=f"device-{QuickdropDevice.objects.count() + 1}",
            label=label,
            user_agent_summary=label,
        )
        return build_device_cookie_value(self.channel, device), device

    def test_landing_renders_pair_qr_and_device_management(self):
        response = self.client.get(reverse("quickdrop:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.channel.slug)
        self.assertContains(response, "PC끼리, 휴대폰끼리, PC와 휴대폰 모두")
        self.assertContains(response, "로그아웃돼도 바로전송은 다시 열 수 있습니다")
        self.assertContains(response, "연결된 기기")
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow, noarchive")
        self.assertIn(DEVICE_COOKIE_NAME, response.cookies)
        self.assertEqual(response.cookies[DEVICE_COOKIE_NAME]["path"], DEVICE_COOKIE_PATH)

    @override_settings(SESSION_COOKIE_SECURE=True)
    def test_device_cookie_uses_secure_flag_when_production_cookies_are_secure(self):
        response = self.client.get(reverse("quickdrop:landing"))

        self.assertTrue(response.cookies[DEVICE_COOKIE_NAME]["secure"])
        self.assertEqual(response.cookies[DEVICE_COOKIE_NAME]["path"], DEVICE_COOKIE_PATH)

    def test_owner_browser_can_reopen_channel_without_login_after_first_visit(self):
        landing_response = self.client.get(
            reverse("quickdrop:landing"),
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )
        owner_cookie = landing_response.cookies[DEVICE_COOKIE_NAME].value

        self.client.logout()
        self.client.cookies[DEVICE_COOKIE_NAME] = owner_cookie

        response = self.client.get(reverse("quickdrop:open"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("quickdrop:channel", kwargs={"slug": self.channel.slug}))

    def test_invalid_pair_token_returns_404(self):
        response = self.client.get(reverse("quickdrop:pair", args=["broken-token"]))
        self.assertEqual(response.status_code, 404)

    def test_pair_post_sets_device_cookie_and_redirects(self):
        token = build_pair_token(self.channel)
        self.client.logout()

        response = self.client.post(
            reverse("quickdrop:pair", args=[token]),
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone)",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("quickdrop:channel", kwargs={"slug": self.channel.slug}))
        self.assertIn(DEVICE_COOKIE_NAME, response.cookies)
        self.assertEqual(response.cookies[DEVICE_COOKIE_NAME]["path"], DEVICE_COOKIE_PATH)
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertEqual(self.channel.devices.filter(revoked_at__isnull=True).count(), 1)

    def test_pair_token_only_allows_latest_link_and_single_successful_pair(self):
        first_token = build_pair_token(self.channel)
        second_token = build_pair_token(self.channel)
        self.client.logout()

        stale_response = self.client.post(
            reverse("quickdrop:pair", args=[first_token]),
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        )
        fresh_response = self.client.post(
            reverse("quickdrop:pair", args=[second_token]),
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone)",
        )
        another_client = self.client_class()
        used_response = another_client.post(
            reverse("quickdrop:pair", args=[second_token]),
            HTTP_USER_AGENT="Mozilla/5.0 (Android)",
        )

        self.assertEqual(stale_response.status_code, 404)
        self.assertEqual(fresh_response.status_code, 302)
        self.assertEqual(used_response.status_code, 404)

    def test_remembered_device_can_open_channel(self):
        self.client.logout()
        cookie_value, _device = self._pair_device_cookie()
        self.client.cookies[DEVICE_COOKIE_NAME] = cookie_value

        response = self.client.get(reverse("quickdrop:channel", kwargs={"slug": self.channel.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-quickdrop-root="true"')
        self.assertContains(response, "붙여넣기나 사진 선택만 하면 됩니다")
        self.assertContains(response, "여기에 붙여넣거나 직접 입력하세요.")
        self.assertContains(response, 'data-quickdrop-history-panel="true"')
        self.assertContains(response, reverse("quickdrop:snapshot", kwargs={"slug": self.channel.slug}))
        self.assertEqual(self.channel.sessions.filter(status=QuickdropSession.STATUS_LIVE).count(), 1)

    def test_snapshot_view_returns_json_for_connected_device(self):
        self.client.logout()
        cookie_value, device = self._pair_device_cookie()
        self.client.cookies[DEVICE_COOKIE_NAME] = cookie_value
        self.client.post(
            reverse("quickdrop:send_text", kwargs={"slug": self.channel.slug}),
            {"text": "실시간 테스트"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        session = self.channel.sessions.get(status=QuickdropSession.STATUS_LIVE)
        device.refresh_from_db()
        previous_seen_at = device.last_seen_at
        previous_updated_at = session.updated_at

        response = self.client.get(
            reverse("quickdrop:snapshot", kwargs={"slug": self.channel.slug}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["session"]["current_text"], "실시간 테스트")
        device.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(device.last_seen_at, previous_seen_at)
        self.assertEqual(session.updated_at, previous_updated_at)

    def test_channel_open_does_not_touch_device_again_within_five_minutes(self):
        self.client.logout()
        cookie_value, device = self._pair_device_cookie()
        recent_seen_at = timezone.now() - timedelta(minutes=1)
        QuickdropDevice.objects.filter(pk=device.pk).update(last_seen_at=recent_seen_at)
        self.client.cookies[DEVICE_COOKIE_NAME] = cookie_value

        response = self.client.get(reverse("quickdrop:channel", kwargs={"slug": self.channel.slug}))

        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertEqual(device.last_seen_at, recent_seen_at)

    def test_owner_channel_uses_teacher_nickname_instead_of_username(self):
        response = self.client.get(reverse("quickdrop:channel", kwargs={"slug": self.channel.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "빠른쌤")
        self.assertNotContains(response, "quickdrop_teacher")

    def test_send_text_replaces_current_payload(self):
        self.client.logout()
        cookie_value, _device = self._pair_device_cookie()
        self.client.cookies[DEVICE_COOKIE_NAME] = cookie_value

        response = self.client.post(
            reverse("quickdrop:send_text", kwargs={"slug": self.channel.slug}),
            {"text": "첫 번째 텍스트"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        session = self.channel.sessions.get(status=QuickdropSession.STATUS_LIVE)
        self.assertEqual(session.current_kind, QuickdropSession.KIND_TEXT)
        self.assertEqual(session.current_text, "첫 번째 텍스트")
        self.assertEqual(QuickdropItem.objects.filter(channel=self.channel).count(), 1)
        self.assertEqual(len(response.json()["session"]["today_items"]), 1)

    def test_second_device_can_replace_same_live_payload(self):
        self.client.logout()
        first_cookie, _first_device = self._pair_device_cookie("교실 PC")
        second_cookie, _second_device = self._pair_device_cookie("개인 휴대폰")

        first_client = self.client_class()
        second_client = self.client_class()
        first_client.cookies[DEVICE_COOKIE_NAME] = first_cookie
        second_client.cookies[DEVICE_COOKIE_NAME] = second_cookie

        first_client.post(
            reverse("quickdrop:send_text", kwargs={"slug": self.channel.slug}),
            {"text": "PC 텍스트"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        second_client.post(
            reverse("quickdrop:send_text", kwargs={"slug": self.channel.slug}),
            {"text": "휴대폰 텍스트"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        live_sessions = self.channel.sessions.filter(status=QuickdropSession.STATUS_LIVE)
        self.assertEqual(live_sessions.count(), 1)
        self.assertEqual(live_sessions.first().current_text, "휴대폰 텍스트")
        self.assertEqual(QuickdropItem.objects.filter(channel=self.channel).count(), 2)

    def test_send_image_and_end_session_clear_today_history(self):
        self.client.logout()
        cookie_value, _device = self._pair_device_cookie()
        self.client.cookies[DEVICE_COOKIE_NAME] = cookie_value

        upload = SimpleUploadedFile("clip.png", PNG_BYTES, content_type="image/png")
        image_response = self.client.post(
            reverse("quickdrop:send_image", kwargs={"slug": self.channel.slug}),
            {"image": upload},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(image_response.status_code, 200)

        session = self.channel.sessions.get(status=QuickdropSession.STATUS_LIVE)
        self.assertEqual(QuickdropItem.objects.filter(channel=self.channel).count(), 1)

        end_response = self.client.post(
            reverse("quickdrop:end_session", kwargs={"slug": self.channel.slug}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(end_response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.status, QuickdropSession.STATUS_ENDED)
        self.assertEqual(session.current_kind, QuickdropSession.KIND_EMPTY)
        self.assertFalse(session.current_text)
        self.assertEqual(QuickdropItem.objects.filter(channel=self.channel).count(), 0)

    def test_session_image_url_requires_channel_access(self):
        self.client.logout()
        cookie_value, _device = self._pair_device_cookie()
        self.client.cookies[DEVICE_COOKIE_NAME] = cookie_value

        upload = SimpleUploadedFile("clip.png", PNG_BYTES, content_type="image/png")
        image_response = self.client.post(
            reverse("quickdrop:send_image", kwargs={"slug": self.channel.slug}),
            {"image": upload},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        image_url = image_response.json()["session"]["current_image_url"]

        blocked_client = self.client_class()
        blocked_response = blocked_client.get(image_url)
        allowed_response = self.client.get(image_url)

        self.assertEqual(blocked_response.status_code, 403)
        self.assertEqual(allowed_response.status_code, 200)
        self.assertEqual(allowed_response.headers["Content-Type"], "image/png")

    def test_opening_channel_after_end_creates_new_live_session(self):
        self.client.logout()
        cookie_value, _device = self._pair_device_cookie()
        self.client.cookies[DEVICE_COOKIE_NAME] = cookie_value

        self.client.post(
            reverse("quickdrop:send_text", kwargs={"slug": self.channel.slug}),
            {"text": "세션 텍스트"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        live_session = self.channel.sessions.get(status=QuickdropSession.STATUS_LIVE)
        live_session.status = QuickdropSession.STATUS_ENDED
        live_session.current_kind = QuickdropSession.KIND_EMPTY
        live_session.current_text = ""
        live_session.ended_at = timezone.now()
        live_session.save(update_fields=["status", "current_kind", "current_text", "ended_at", "updated_at"])

        response = self.client.get(reverse("quickdrop:channel", kwargs={"slug": self.channel.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.channel.sessions.filter(status=QuickdropSession.STATUS_LIVE).count(), 1)

    def test_manifest_exposes_share_target(self):
        response = self.client.get(reverse("quickdrop:manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "share_target")
        self.assertContains(response, reverse("quickdrop:share_target"))

    def test_pair_page_uses_public_service_name(self):
        token = build_pair_token(self.channel)
        self.client.logout()

        response = self.client.get(reverse("quickdrop:pair", args=[token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "바로전송")
        self.assertNotContains(response, ">quickdrop<", html=False)

    def test_share_target_uses_remembered_device_cookie(self):
        self.client.logout()
        cookie_value, _device = self._pair_device_cookie()
        self.client.cookies[DEVICE_COOKIE_NAME] = cookie_value

        response = self.client.post(
            reverse("quickdrop:share_target"),
            {"shared_text": "공유시트 텍스트"},
        )

        self.assertEqual(response.status_code, 302)
        session = self.channel.sessions.get(status=QuickdropSession.STATUS_LIVE)
        self.assertEqual(session.current_text, "공유시트 텍스트")
        self.assertEqual(QuickdropItem.objects.filter(channel=self.channel).count(), 1)

    def test_share_target_can_replace_with_image(self):
        self.client.logout()
        cookie_value, _device = self._pair_device_cookie("갤럭시")
        self.client.cookies[DEVICE_COOKIE_NAME] = cookie_value

        response = self.client.post(
            reverse("quickdrop:share_target"),
            {"shared_file": SimpleUploadedFile("shared.png", PNG_BYTES, content_type="image/png")},
        )

        self.assertEqual(response.status_code, 302)
        session = self.channel.sessions.get(status=QuickdropSession.STATUS_LIVE)
        self.assertEqual(session.current_kind, QuickdropSession.KIND_IMAGE)
        self.assertEqual(QuickdropItem.objects.filter(channel=self.channel).count(), 1)

    def test_cleanup_command_clears_previous_day_history(self):
        session = QuickdropSession.objects.create(
            channel=self.channel,
            status=QuickdropSession.STATUS_LIVE,
            current_kind=QuickdropSession.KIND_TEXT,
            current_text="남은 내용",
            last_activity_at=timezone.now() - timedelta(days=1, minutes=5),
        )
        item = QuickdropItem.objects.create(
            channel=self.channel,
            sender_label="교실 PC",
            kind=QuickdropItem.KIND_TEXT,
            text="어제 기록",
            mime_type="text/plain",
        )
        stale_at = timezone.now() - timedelta(days=1, minutes=5)
        QuickdropItem.objects.filter(pk=item.pk).update(created_at=stale_at)
        QuickdropSession.objects.filter(pk=session.pk).update(last_activity_at=stale_at)

        from django.core.management import call_command

        call_command("cleanup_quickdrop")

        session.refresh_from_db()
        self.assertEqual(session.status, QuickdropSession.STATUS_ENDED)
        self.assertFalse(session.current_text)
        self.assertEqual(QuickdropItem.objects.filter(channel=self.channel).count(), 0)

    def test_landing_does_not_cleanup_previous_day_history_inline(self):
        stale_item = QuickdropItem.objects.create(
            channel=self.channel,
            sender_label="교실 PC",
            kind=QuickdropItem.KIND_TEXT,
            text="어제 기록",
            mime_type="text/plain",
        )
        stale_at = timezone.now() - timedelta(days=1, minutes=5)
        QuickdropItem.objects.filter(pk=stale_item.pk).update(created_at=stale_at)

        response = self.client.get(reverse("quickdrop:landing"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(QuickdropItem.objects.filter(channel=self.channel).count(), 1)

    def test_service_launcher_payload_includes_quickdrop_in_today_operations(self):
        Product.objects.create(
            title="바로전송",
            lead_text="빠른 전송",
            description="개인 전용 즉시 전송 통로",
            price=0,
            is_active=True,
            is_guest_allowed=False,
            icon="⚡",
            service_type="classroom",
            launch_route_name="quickdrop:landing",
            solve_text="내 폰과 PC 사이에 텍스트나 이미지를 바로 옮기고 싶어요",
        )

        request = self.factory.get("/")
        request.user = self.user

        payload = search_products(request)["service_launcher_json"]

        import json

        items = json.loads(payload)
        quickdrop = next(item for item in items if item["title"] == "바로전송")
        self.assertEqual(quickdrop["group_key"], "class_ops")
        self.assertEqual(quickdrop["href"], reverse("quickdrop:landing"))
