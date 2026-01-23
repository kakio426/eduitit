from django.test import TestCase
from allauth.socialaccount.providers import registry

class SocialProviderTestCase(TestCase):
    def test_kakao_provider_registered(self):
        """카카오 소셜 공급자가 등록되어 있는지 확인"""
        self.assertTrue(registry.get_class('kakao'), "카카오 공급자가 등록되지 않았습니다.")

    def test_naver_provider_registered(self):
        """네이버 소셜 공급자가 등록되어 있는지 확인"""
        self.assertTrue(registry.get_class('naver'), "네이버 공급자가 등록되지 않았습니다.")
