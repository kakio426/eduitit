import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import HomeAgentQuotaState, HomeAgentUsageLog, UserProfile


User = get_user_model()


def _create_user(username):
    user = User.objects.create_user(
        username=username,
        password="pass1234",
        email=f"{username}@example.com",
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = username
    profile.role = "school"
    profile.save(update_fields=["nickname", "role"])
    return user


class HomeAgentQuotaTests(TestCase):
    def setUp(self):
        self.user = _create_user("quotauser")
        self.client.force_login(self.user)

    @patch(
        "core.views.generate_home_agent_preview",
        return_value={
            "preview": {
                "badge": "알림장",
                "title": "알림장 초안",
                "summary": "요약",
                "sections": [{"title": "핵심", "items": ["준비물 안내"]}],
                "note": "확인",
            },
            "provider": "deepseek",
            "model": "deepseek-chat",
        },
    )
    def test_home_agent_preview_records_usage_after_success(self, _mock_generate_preview):
        response = self.client.post(
            reverse("home_agent_preview"),
            data=json.dumps({"mode_key": "notice", "text": "준비물 안내"}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(HomeAgentUsageLog.objects.filter(user=self.user).count(), 1)
        usage = HomeAgentUsageLog.objects.get(user=self.user)
        self.assertEqual(usage.mode_key, "notice")
        self.assertEqual(usage.provider, "deepseek")

    def test_home_agent_preview_returns_limit_modal_payload_when_daily_limit_reached(self):
        HomeAgentUsageLog.objects.bulk_create(
            [
                HomeAgentUsageLog(
                    user=self.user,
                    usage_date=timezone.localdate(),
                    mode_key="notice",
                    provider="deepseek",
                )
                for _ in range(15)
            ]
        )

        response = self.client.post(
            reverse("home_agent_preview"),
            data=json.dumps({"mode_key": "notice", "text": "준비물 안내"}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 429)
        payload = response.json()
        self.assertEqual(payload["error_code"], "home_agent_quota_exceeded")
        self.assertIn(reverse("messagebox:developer_chat"), payload["quota"]["action_href"])
        self.assertEqual(payload["quota"]["chip_label"], "한도 요청")
        self.assertIn("인디스쿨 함께 사용하기", payload["quota"]["message"])
        state = HomeAgentQuotaState.objects.get(user=self.user)
        self.assertIsNotNone(state.last_limit_reached_at)
        self.assertIsNone(state.prompt_dismissed_at)

    def test_home_agent_quota_dismiss_returns_visible_nav_action(self):
        HomeAgentQuotaState.objects.create(
            user=self.user,
            last_limit_reached_at=timezone.now(),
        )

        response = self.client.post(reverse("home_agent_quota_dismiss"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["nav_action"]["visible"])
        self.assertEqual(payload["nav_action"]["label"], "한도 요청")

        home_response = self.client.get(reverse("home"))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, 'data-home-agent-limit-chip="true"')
        self.assertContains(home_response, "한도 요청")

    def test_home_v6_script_contains_quota_modal_flow(self):
        script = (
            settings.BASE_DIR
            / "core"
            / "static"
            / "core"
            / "js"
            / "home_authenticated_v6.js"
        ).read_text(encoding="utf-8")

        self.assertIn("home_agent_quota_exceeded", script)
        self.assertIn("revealHomeAgentLimitNavChip", script)
        self.assertIn("goToHomeAgentLimitChat", script)
