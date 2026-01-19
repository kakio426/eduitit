"""
Test 1.1 & 1.2: Production settings 로딩 및 환경변수 기반 DB 연결 테스트
RED Phase - 이 테스트는 config/settings_production.py가 없으므로 실패해야 함
"""
import os
from django.test import TestCase, override_settings


class ProductionSettingsTest(TestCase):
    """Test 1.1: settings_production.py 로딩 테스트"""
    
    def test_production_settings_module_exists(self):
        """Production 설정 모듈이 존재하고 import 가능해야 함"""
        try:
            from config import settings_production
            self.assertTrue(hasattr(settings_production, 'DEBUG'))
            self.assertFalse(settings_production.DEBUG)  # Production에서는 DEBUG=False
        except ImportError:
            self.fail("config.settings_production 모듈을 import할 수 없습니다")
    
    def test_secret_key_from_environment(self):
        """SECRET_KEY가 환경변수에서 로드되어야 함"""
        from config import settings_production
        # Production에서는 하드코딩된 키 대신 환경변수 사용
        self.assertNotIn('insecure', settings_production.SECRET_KEY.lower())
    
    def test_allowed_hosts_configured(self):
        """ALLOWED_HOSTS가 설정되어 있어야 함"""
        from config import settings_production
        self.assertTrue(len(settings_production.ALLOWED_HOSTS) > 0)


class DatabaseConfigTest(TestCase):
    """Test 1.2: 환경변수 기반 DB 연결 테스트"""
    
    def test_database_url_support(self):
        """DATABASE_URL 환경변수 지원 확인"""
        from config import settings_production
        # dj-database-url을 사용하여 DATABASE_URL 파싱 가능해야 함
        self.assertIn('default', settings_production.DATABASES)
    
    def test_postgresql_engine_for_production(self):
        """Production에서 PostgreSQL 엔진 사용 확인"""
        # 환경변수가 설정된 경우에만 테스트
        if os.environ.get('DATABASE_URL'):
            from config import settings_production
            engine = settings_production.DATABASES['default']['ENGINE']
            self.assertIn('postgresql', engine)
