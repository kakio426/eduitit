from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.guide_links import SERVICE_GUIDE_PADLET_URL
from core.models import UserPolicyConsent, UserProfile
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from happy_seed.models import HSClassroom


class UIAuthTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ui_user",
            password="password123",
            email="ui_user@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "test-teacher"
        profile.role = ""
        profile.save()
        UserPolicyConsent.objects.create(
            user=self.user,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source="required_gate",
        )
        self.client.login(username="ui_user", password="password123")

    def test_role_selection_page_content(self):
        response = self.client.get(reverse("select_role"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "school")
        self.assertContains(response, "instructor")
        self.assertContains(response, "company")

    def test_login_page_social_buttons_placeholder(self):
        self.client.logout()
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "이 도구는 로그인 후 이어집니다")
        self.assertContains(response, "내 일정과 학급 설정 저장")
        self.assertContains(response, "제출 결과와 기록 보호")
        self.assertContains(response, "데모 둘러보기")
        self.assertContains(response, "가이드 보기")
        self.assertContains(response, "카카오톡으로 시작하기")
        self.assertContains(response, "네이버로 시작하기")
        self.assertContains(response, "최초 1회 이용약관 및 개인정보처리방침 동의가 필요합니다")
        self.assertContains(response, "운영정책")
        self.assertContains(response, SERVICE_GUIDE_PADLET_URL)
        self.assertContains(response, f'{reverse("home")}#guest-home-try-now')
        self.assertNotContains(response, "관리자 접속")
        self.assertNotContains(response, "bot_login_input")
        self.assertNotContains(response, "bot_password_input")
        self.assertNotContains(response, "bot_login_submit")

    def test_home_nav_keeps_dropdown_shell_visible_for_classroom_shortcuts(self):
        profile = UserProfile.objects.get(user=self.user)
        profile.role = "school"
        profile.save(update_fields=["role"])
        classroom = HSClassroom.objects.create(teacher=self.user, name="3학년 2반")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "clay-card--overflow-visible")
        self.assertContains(response, 'id="desktopClassroomPicker"')
        self.assertContains(response, 'id="classroomMenuBtn"')
        self.assertContains(response, 'id="desktopClassroomMenu"')
        self.assertContains(response, 'data-classroom-select="true"')
        self.assertContains(response, f'data-classroom-id="{classroom.pk}"')
        self.assertContains(response, "3학년 2반")
        self.assertContains(response, 'data-classroom-clear="true"')
        self.assertNotContains(response, 'x-data="classroomPicker()"')
