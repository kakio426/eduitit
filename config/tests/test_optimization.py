from django.test import TestCase
import os
from django.conf import settings

class FrontendOptimizationTest(TestCase):
    def test_production_static_compression(self):
        """Production 설정에서 정적 파일 압축이 활성화되어 있어야 함"""
        # settings_production.py를 직접 임포트하여 확인
        from config import settings_production
        
        backend = settings_production.STORAGES['staticfiles']['BACKEND']
        self.assertEqual(
            backend, 
            'whitenoise.storage.CompressedManifestStaticFilesStorage',
            "WhiteNoise 압축 및 매니페스트 스토리지가 설정되지 않았습니다."
        )

    def test_production_security_headers(self):
        """Production 보안 헤더 설정 확인"""
        from config import settings_production
        
        # DEBUG가 False일 때 보안 필터가 켜져 있는지 확인
        if not settings_production.DEBUG:
            self.assertTrue(settings_production.SECURE_BROWSER_XSS_FILTER)
            self.assertTrue(settings_production.SECURE_CONTENT_TYPE_NOSNIFF)
