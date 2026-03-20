from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from core.models import SiteConfig, UserMarketingEmailConsent


class SiteConfigTestCase(TestCase):
    def test_site_config_load_returns_singleton(self):
        """Test that SiteConfig.load always returns the singleton row."""
        config = SiteConfig.load()
        config.banner_text = "안내 배너"
        config.save(update_fields=["banner_text"])

        config_reloaded = SiteConfig.load()
        self.assertEqual(config.pk, config_reloaded.pk)
        self.assertEqual(config_reloaded.banner_text, "안내 배너")


class UserProfileTestCase(TestCase):
    def test_pinned_notice_expanded_can_be_set_per_user(self):
        """Test that pinned notice expansion state is stored per user profile."""
        user = User.objects.create_user(username='profileuser', password='pass1234')
        profile = user.userprofile
        profile.pinned_notice_expanded = True
        profile.save(update_fields=['pinned_notice_expanded'])

        self.assertTrue(User.objects.get(pk=user.pk).userprofile.pinned_notice_expanded)


class UserMarketingEmailConsentTestCase(TestCase):
    def test_is_active_is_true_without_revoked_at(self):
        user = User.objects.create_user(username='marketinguser', password='pass1234')
        consent = UserMarketingEmailConsent.objects.create(
            user=user,
            consented_at=timezone.now(),
            consent_source='social_signup',
        )

        self.assertTrue(consent.is_active)

    def test_is_active_is_false_after_revocation(self):
        user = User.objects.create_user(username='marketingrevoked', password='pass1234')
        consent = UserMarketingEmailConsent.objects.create(
            user=user,
            consented_at=timezone.now(),
            consent_source='social_signup',
            revoked_at=timezone.now(),
        )

        self.assertFalse(consent.is_active)
