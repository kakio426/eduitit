from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class SignatureMakerTeacherFirstTests(TestCase):
    def test_guest_view_promotes_work_first_actions_without_old_hero_copy(self):
        response = self.client.get(reverse("signatures:maker"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "이름만 넣고 폰트형 서명 이미지를 만듭니다")
        self.assertContains(response, "직접 쓴 손서명이 기본이고")
        self.assertContains(response, "이미지 저장")
        self.assertContains(response, "보관함 쓰려면 계정 만들기")
        self.assertContains(response, "서명 목록으로")
        self.assertContains(response, "보관함은 나중에 켜기")
        self.assertNotContains(response, "연수 서명으로 돌아가기")
        self.assertNotContains(response, "선생님만의 멋진 전자 서명을 1초 만에 만들어보세요.")

    def test_authenticated_view_checks_response_ok_before_success_message(self):
        user = User.objects.create_user(
            username="sign_teacher",
            password="pw123456",
            email="sign_teacher@example.com",
        )
        user.userprofile.nickname = "서명교사"
        user.userprofile.role = "school"
        user.userprofile.save(update_fields=["nickname", "role"])
        self.client.force_login(user)

        response = self.client.get(reverse("signatures:maker"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "폰트 스타일 저장")
        self.assertContains(response, "내 서명 보관함 보기")
        self.assertContains(response, "폰트 스타일을 저장했습니다.", html=False)
        self.assertContains(response, "response.ok", html=False)

    def test_authenticated_view_applies_saved_style_query_params(self):
        user = User.objects.create_user(
            username="sign_teacher_with_style",
            password="pw123456",
            email="sign_teacher_with_style@example.com",
        )
        user.userprofile.nickname = "서명교사"
        user.userprofile.role = "school"
        user.userprofile.save(update_fields=["nickname", "role"])
        self.client.force_login(user)

        response = self.client.get(
            reverse("signatures:maker"),
            data={"font": "Gowun Batang", "color": "#1e40af"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "font-family: 'Gowun Batang'")
        self.assertContains(response, 'value="#1e40af"', html=False)
