from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import UserProfile

class UIAuthTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ui_user',
            password='password123',
            email='ui_user@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = '테스트교사'
        profile.role = ''
        profile.save()
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
        self.client.logout()
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '카카오톡으로 시작하기')
        self.assertContains(response, '네이버로 시작하기')
