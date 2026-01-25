from django.test import TestCase
from django.contrib.auth.models import User
from fortune.models import Stem, Branch, SixtyJiazi, SajuProfile, NatalChart
from django.utils import timezone

class FortuneModelTests(TestCase):
    def test_stem_model_creation(self):
        """Test Stem model creation"""
        try:
            stem = Stem.objects.create(name="Gap", character="甲", polarity="yang", element="wood")
            self.assertEqual(str(stem), "甲")
        except NameError:
            self.fail("Stem model not defined")
        except Exception as e:
            self.fail(f"Stem creation failed: {e}")

    def test_branch_model_creation(self):
        """Test Branch model creation"""
        try:
            branch = Branch.objects.create(name="Ja", character="子", polarity="yang", element="water")
            self.assertEqual(str(branch), "子")
        except NameError:
            self.fail("Branch model not defined")

    def test_sixty_jiazi_model_creation(self):
        """Test SixtyJiazi model creation"""
        try:
            stem = Stem.objects.create(name="Gap", character="甲", polarity="yang", element="wood")
            branch = Branch.objects.create(name="Ja", character="子", polarity="yang", element="water")
            jiazi = SixtyJiazi.objects.create(stem=stem, branch=branch, name="GapJa", na_yin_element="Sea Gold")
            self.assertEqual(str(jiazi), "甲子")
        except NameError:
            self.fail("SixtyJiazi model not defined")

    def test_saju_profile_creation(self):
        """Test SajuProfile model creation"""
        try:
            user = User.objects.create_user(username="testuser", password="password")
            profile = SajuProfile.objects.create(
                user=user,
                birth_date_gregorian=timezone.now(),
                gender="M",
                birth_city="Seoul",
                longitude=127.0
            )
            self.assertEqual(profile.user.username, "testuser")
            self.assertEqual(profile.birth_city, "Seoul")
        except NameError:
            self.fail("SajuProfile model not defined")

    def test_natal_chart_model_creation(self):
        """Test NatalChart model creation"""
        try:
            user = User.objects.create_user(username="chartuser", password="password")
            profile = SajuProfile.objects.create(
                user=user, 
                gender="F", 
                birth_date_gregorian=timezone.now(),
                birth_city="Seoul",
                longitude=127.0
            )
            
            stem = Stem.objects.create(name="Gap", character="甲", polarity="yang", element="wood")
            branch = Branch.objects.create(name="Ja", character="子", polarity="yang", element="water")
            
            chart = NatalChart.objects.create(
                saju_profile=profile,
                year_stem=stem, year_branch=branch,
                month_stem=stem, month_branch=branch,
                day_stem=stem, day_branch=branch,
                hour_stem=stem, hour_branch=branch,
                day_master_strength="Weak"
            )
            self.assertEqual(chart.saju_profile, profile)
            self.assertEqual(chart.year_stem.character, "甲")
        except NameError:
            self.fail("NatalChart model not defined")
