from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from fortune.models import FortunePseudonymousCache

User = get_user_model()


class TestCleanupCommand(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test', password='pw')

    def test_cleanup_deletes_only_expired_pseudonymous_cache(self):
        expired = FortunePseudonymousCache.objects.create(
            user=self.user,
            purpose='full',
            fingerprint='expired',
            result_text='old result',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        valid = FortunePseudonymousCache.objects.create(
            user=self.user,
            purpose='daily',
            fingerprint='valid',
            result_text='new result',
            expires_at=timezone.now() + timedelta(days=1),
        )

        out = StringIO()
        call_command('cleanup_old_sessions', stdout=out)

        self.assertFalse(FortunePseudonymousCache.objects.filter(id=expired.id).exists())
        self.assertTrue(FortunePseudonymousCache.objects.filter(id=valid.id).exists())
        self.assertIn("Successfully deleted", out.getvalue())
