"""
Test 1.1 & 1.2: Production settings 로딩 및 환경변수 기반 DB 연결 테스트
RED Phase - 이 테스트는 config/settings_production.py가 없으므로 실패해야 함
"""
import importlib
import os
import sys
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
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
        with patch.dict(os.environ, {"SECRET_KEY": "env-secret-key"}, clear=False):
            reloaded = importlib.reload(settings_production)
            self.assertEqual(reloaded.SECRET_KEY, "env-secret-key")

        importlib.reload(settings_production)

    def test_production_settings_prefers_secret_key_environment_variable(self):
        """Render에서 쓰는 SECRET_KEY 환경변수를 우선 사용해야 함"""
        from config import settings_production

        with patch.dict(os.environ, {"SECRET_KEY": "render-secret-key", "DJANGO_SECRET_KEY": "legacy-secret-key"}, clear=False):
            reloaded = importlib.reload(settings_production)
            self.assertEqual(reloaded.SECRET_KEY, "render-secret-key")

        importlib.reload(settings_production)

    def test_production_settings_requires_secret_key_outside_tests(self):
        """테스트 실행이 아닐 때는 production SECRET_KEY가 반드시 있어야 함"""
        from config import settings_production

        with patch.dict(os.environ, {"SECRET_KEY": "   ", "DJANGO_SECRET_KEY": "\t"}, clear=False):
            with patch.object(sys, "argv", ["gunicorn"]):
                with self.assertRaises(ImproperlyConfigured):
                    importlib.reload(settings_production)

        importlib.reload(settings_production)
    
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


class ProductionCostControlSettingsTest(TestCase):
    def _settings_snapshot_with_env(self, env):
        from config import settings_production

        try:
            with patch.dict(os.environ, {"SECRET_KEY": "test-secret-key", **env}, clear=True):
                reloaded = importlib.reload(settings_production)
                return {
                    "VISITOR_TRACKING_ENABLED": reloaded.VISITOR_TRACKING_ENABLED,
                    "CACHES_DEFAULT": dict(reloaded.CACHES["default"]),
                }
        finally:
            importlib.reload(settings_production)

    def test_visitor_tracking_is_disabled_by_default(self):
        snapshot = self._settings_snapshot_with_env({})

        self.assertFalse(snapshot["VISITOR_TRACKING_ENABLED"])

    def test_visitor_tracking_can_be_reenabled_by_environment(self):
        snapshot = self._settings_snapshot_with_env({"VISITOR_TRACKING_ENABLED": "true"})

        self.assertTrue(snapshot["VISITOR_TRACKING_ENABLED"])

    def test_auto_cache_uses_redis_when_redis_url_is_set(self):
        snapshot = self._settings_snapshot_with_env({
            "CACHE_BACKEND": "auto",
            "REDIS_URL": "redis://localhost:6379/0",
        })

        self.assertEqual(
            snapshot["CACHES_DEFAULT"]["BACKEND"],
            "django.core.cache.backends.redis.RedisCache",
        )
        self.assertEqual(snapshot["CACHES_DEFAULT"]["LOCATION"], "redis://localhost:6379/0")

    def test_auto_cache_uses_locmem_without_redis_url(self):
        snapshot = self._settings_snapshot_with_env({"CACHE_BACKEND": "auto"})

        self.assertEqual(
            snapshot["CACHES_DEFAULT"]["BACKEND"],
            "django.core.cache.backends.locmem.LocMemCache",
        )

    def test_locmem_cache_override_ignores_redis_url(self):
        snapshot = self._settings_snapshot_with_env({
            "CACHE_BACKEND": "locmem",
            "REDIS_URL": "redis://localhost:6379/0",
        })

        self.assertEqual(
            snapshot["CACHES_DEFAULT"]["BACKEND"],
            "django.core.cache.backends.locmem.LocMemCache",
        )

    def test_database_cache_override_keeps_last_resort_rollback_path(self):
        snapshot = self._settings_snapshot_with_env({"CACHE_BACKEND": "database"})

        self.assertEqual(
            snapshot["CACHES_DEFAULT"]["BACKEND"],
            "django.core.cache.backends.db.DatabaseCache",
        )
