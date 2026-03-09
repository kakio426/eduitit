from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class ConsentTeacherFirstDashboardTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="consent_teacher",
            password="pw123456",
            email="consent_teacher@example.com",
        )
        self.teacher.userprofile.nickname = "동의교사"
        self.teacher.userprofile.role = "school"
        self.teacher.userprofile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.teacher)

    def test_dashboard_demotes_policy_panel_and_keeps_primary_action_first(self):
        response = self.client.get(reverse("consent:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "동의서 보내기와 결과 확인")
        self.assertContains(response, "새 동의서 만들기")
        self.assertContains(response, "업무 기준과 법령 보기")
        self.assertNotContains(response, "문서 업로드부터 발송 링크 관리까지 한 화면에서 관리합니다.")
