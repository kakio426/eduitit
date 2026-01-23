from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

class UIAuthTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ui_user', password='password123')
        self.client.login(username='ui_user', password='password123')

    def test_role_selection_page_content(self):
        """역할 선택 페이지가 정상적으로 렌더링되고 옵션이 있는지 확인"""
        response = self.client.get(reverse('select_role'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'school')
        self.assertContains(response, 'instructor')
        self.assertContains(response, 'company')

    def test_login_page_social_buttons_placeholder(self):
        """로그인 페이지에 소셜 로그인 버튼이 있는지 확인"""
        response = self.client.get('/accounts/login/')
        # allauth가 설정되었으므로 socialaccount 관련 링크가 있어야 함
        self.assertContains(response, 'kakao')
        self.assertContains(response, 'naver')
