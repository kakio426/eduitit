import jwt
import datetime
from django.test import TestCase
from django.contrib.auth.models import User
from django.conf import settings
from core.utils import generate_sso_token

class SSOTokenTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='teacher1', password='password123')
        
    def test_user_has_role(self):
        """유저가 역할을 가질 수 있는지 테스트"""
        self.user.userprofile.role = 'school'
        self.user.userprofile.save()
        self.assertEqual(self.user.userprofile.role, 'school')

    def test_sso_token_generation_with_role(self):
        """실제 유틸리티를 사용한 JWT 생성 테스트"""
        self.user.userprofile.role = 'instructor'
        self.user.userprofile.save()
        
        token = generate_sso_token(self.user)
        
        # Decode and verify
        decoded = jwt.decode(token, settings.SSO_JWT_SECRET, algorithms=['HS256'])
        self.assertEqual(decoded['role'], 'instructor')
        self.assertEqual(decoded['username'], 'teacher1')
