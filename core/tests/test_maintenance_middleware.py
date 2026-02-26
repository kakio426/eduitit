from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import SiteConfig, UserProfile


def _create_onboarded_superuser():
    user = User.objects.create_superuser(
        username='admin',
        email='admin@test.com',
        password='pass1234',
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = 'admin'
    profile.role = 'school'
    profile.save()
    return user


@override_settings(MAINTENANCE_MODE=False)
class MaintenanceModeMiddlewareSiteConfigTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_site_config_maintenance_blocks_anonymous_users(self):
        config = SiteConfig.load()
        config.maintenance_mode = True
        config.save()

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, '잠시 점검 중입니다', status_code=503)

    def test_site_config_maintenance_allows_superuser(self):
        config = SiteConfig.load()
        config.maintenance_mode = True
        config.save()
        _create_onboarded_superuser()
        self.client.login(username='admin', password='pass1234')

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

    def test_site_config_maintenance_keeps_admin_login_accessible(self):
        config = SiteConfig.load()
        config.maintenance_mode = True
        config.save()

        response = self.client.get('/accounts/login/')

        self.assertNotEqual(response.status_code, 503)

    def test_site_config_maintenance_off_keeps_site_available(self):
        config = SiteConfig.load()
        config.maintenance_mode = False
        config.save()

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)


@override_settings(MAINTENANCE_MODE=True)
class MaintenanceModeMiddlewareEnvVarPriorityTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_env_maintenance_blocks_even_when_site_config_off(self):
        config = SiteConfig.load()
        config.maintenance_mode = False
        config.save()

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 503)
