from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
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
        self.assertContains(response, "카카오톡으로 시작하기")
        self.assertContains(response, "네이버로 시작하기")
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
