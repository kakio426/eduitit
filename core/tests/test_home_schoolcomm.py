from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from schoolcomm.services import create_workspace_for_user


User = get_user_model()


@override_settings(HOME_LAYOUT_VERSION="v5", HOME_V2_ENABLED=True)
class HomeSchoolcommCardTests(TestCase):
    def test_home_renders_schoolcomm_as_separate_card_and_keeps_quickdrop_panel(self):
        call_command("ensure_quickdrop")
        call_command("ensure_schoolcomm")
        user = User.objects.create_user(username="homecard", email="homecard@test.com", password="pw123456")
        user.userprofile.nickname = "홈카드교사"
        user.userprofile.role = "school"
        user.userprofile.save(update_fields=["nickname", "role"])
        UserPolicyConsent.objects.create(
            user=user,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source="required_gate",
        )
        create_workspace_for_user(user, name="홈테스트초")
        self.client.login(username="homecard", password="pw123456")

        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home_authenticated_v5.html")
        self.assertContains(response, "우리끼리 채팅방")
        self.assertContains(response, "바로전송")
        self.assertIn('data-home-schoolcomm-card="desktop"', content)
        self.assertIn('data-home-v4-quickdrop-panel="true"', content)
        self.assertIn(reverse("schoolcomm:main"), content)
