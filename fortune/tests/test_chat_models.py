from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from fortune.models import FortunePseudonymousCache

User = get_user_model()


class TestFortunePseudonymousCacheModel(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')

    def test_cache_creation(self):
        cache_entry = FortunePseudonymousCache.objects.create(
            user=self.user,
            purpose='full',
            fingerprint='a' * 64,
            result_text='scrubbed result',
            expires_at=timezone.now() + timedelta(days=30),
        )

        self.assertIsNotNone(cache_entry.id)
        self.assertEqual(cache_entry.user, self.user)
        self.assertEqual(cache_entry.purpose, 'full')
        self.assertEqual(str(cache_entry), f"{self.user.username} full cache")

    def test_cache_unique_constraint_is_user_scoped(self):
        FortunePseudonymousCache.objects.create(
            user=self.user,
            purpose='full',
            fingerprint='dup',
            result_text='one',
            expires_at=timezone.now() + timedelta(days=30),
        )

        with self.assertRaises(IntegrityError):
            FortunePseudonymousCache.objects.create(
                user=self.user,
                purpose='full',
                fingerprint='dup',
                result_text='two',
                expires_at=timezone.now() + timedelta(days=30),
            )
