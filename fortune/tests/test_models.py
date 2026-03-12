from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from fortune.models import Branch, FortunePseudonymousCache, FortuneResult, SixtyJiazi, Stem


class FortuneModelTests(TestCase):
    def test_stem_model_creation(self):
        stem = Stem.objects.create(name="Gap", character="甲", polarity="yang", element="wood")
        self.assertEqual(str(stem), "甲")

    def test_branch_model_creation(self):
        branch = Branch.objects.create(name="Ja", character="子", polarity="yang", element="water")
        self.assertEqual(str(branch), "子")

    def test_sixty_jiazi_model_creation(self):
        stem = Stem.objects.create(name="Gap", character="甲", polarity="yang", element="wood")
        branch = Branch.objects.create(name="Ja", character="子", polarity="yang", element="water")
        jiazi = SixtyJiazi.objects.create(stem=stem, branch=branch, name="GapJa", na_yin_element="Sea Gold")
        self.assertEqual(str(jiazi), "甲子")

    def test_fortune_result_creation_without_natal_chart(self):
        user = User.objects.create_user(username="testuser", password="password")
        result = FortuneResult.objects.create(
            user=user,
            mode="teacher",
            result_text="저장 가능한 결과",
        )

        self.assertEqual(result.user.username, "testuser")
        self.assertEqual(result.result_text, "저장 가능한 결과")

    def test_pseudonymous_cache_creation(self):
        user = User.objects.create_user(username="cacheuser", password="password")
        cache = FortunePseudonymousCache.objects.create(
            user=user,
            purpose="daily",
            fingerprint="f" * 64,
            result_text="비식별 결과",
            expires_at=timezone.now() + timedelta(days=30),
        )

        self.assertEqual(cache.user, user)
        self.assertEqual(cache.purpose, "daily")
