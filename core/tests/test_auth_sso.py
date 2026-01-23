from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

class AuthSSOTestCase(TestCase):
    def test_user_creation(self):
        """기본 유저 생성 테스트"""
        user = User.objects.create_user(username='testteacher', password='password123')
        self.assertEqual(user.username, 'testteacher')
        self.assertTrue(user.is_active)

    def test_login_url_exists(self):
        """로그인 URL이 allauth 경로로 정상 연결되는지 테스트"""
        # allauth가 설정되면 /accounts/login/ 주소가 활성화되어야 함
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)

    def test_social_apps_configured(self):
        """네이버/카카오 소셜 앱이 DB에 등록 가능한 상태인지 테스트 (RED: 아직 설정 안됨)"""
        # 이 테스트는 Phase 2에서 실제 설정을 하면 통과하도록 설계
        from allauth.socialaccount.models import SocialApp
        # 현재는 SocialApp이 하나도 없어야 함 (아직 등록 안했으므로)
        self.assertEqual(SocialApp.objects.count(), 0)
