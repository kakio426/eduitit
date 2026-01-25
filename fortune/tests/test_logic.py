from django.test import TestCase
from django.utils import timezone
from datetime import datetime
import pytz
from fortune.libs import calculator, manse
from fortune.models import Stem, Branch

class LogicEngineTests(TestCase):
    def setUp(self):
        # Seed basic stems/branches for testing
        stems_data = [
            ('Gap', '甲', 'yang', 'wood'), ('Eul', '乙', 'yin', 'wood'),
            ('Byung', '丙', 'yang', 'fire'), ('Jung', '丁', 'yin', 'fire'),
            ('Moo', '戊', 'yang', 'earth'), ('Gi', '己', 'yin', 'earth'),
            ('Gyung', '庚', 'yang', 'metal'), ('Shin', '辛', 'yin', 'metal'),
            ('Im', '壬', 'yang', 'water'), ('Gye', '癸', 'yin', 'water')
        ]
        branches_data = [
            ('Ja', '子', 'yang', 'water'), ('Chuk', '丑', 'yin', 'earth'),
            ('In', '寅', 'yang', 'wood'), ('Myo', '卯', 'yin', 'wood'),
            ('Jin', '辰', 'yang', 'earth'), ('Sa', '巳', 'yin', 'fire'),
            ('O', '午', 'yang', 'fire'), ('Mi', '未', 'yin', 'earth'),
            ('Shin', '申', 'yang', 'metal'), ('Yoo', '酉', 'yin', 'metal'),
            ('Sool', '戌', 'yang', 'earth'), ('Hae', '亥', 'yin', 'water')
        ]
        
        for n, c, p, e in stems_data: Stem.objects.create(name=n, character=c, polarity=p, element=e)
        for n, c, p, e in branches_data: Branch.objects.create(name=n, character=c, polarity=p, element=e)

    def test_calculate_pillars_standard(self):
        """
        Test standard calculation.
        Solar Date: 2024-05-05 14:30
        Year: 甲辰 (Gap-Jin)
        Month: 戊辰 (Moo-Jin) (Lichun passed, Ipha passed on May 5?)
        Day: 己巳 (Gi-Sa) (Random example, need real verification)
        Hour: 辛未 (Shin-Mi)
        """
        # We need a reference value. Let's pick a known date.
        # 1990-05-05 14:30 (KST)
        # Year: Geng-Wu (庚午)
        # Month: Xin-Si (辛巳) - Ipha is May 6 in 1990? Check manse.
        # Day: Bing-Yin (丙寅)
        # Hour: Yi-Wei (乙未) - 13:30~15:30 is Mi term.
        # Day Stem Bing (丙) -> Hour stem start from 戊(Moo)? 
        # Bing/Xin day -> Rat hour is Moo-Ja.
        # Moo-Ja -> Gi-Chuk -> Geng-In -> Xin-Myo -> Ren-Jin -> Gui-Sa -> Jia-Wu -> Yi-Wei. Correct.
        
        # We will trust the Calculator logic if unit tests pass
        # Here we just check it returns 4 pillars structure.
        
        dt = datetime(1990, 5, 5, 14, 30, tzinfo=pytz.timezone('Asia/Seoul'))
        pillars = calculator.get_pillars(dt)
        
        self.assertEqual(pillars['year']['stem'].character, '庚')
        self.assertEqual(pillars['year']['branch'].character, '午')
        # Month might vary depending on exact minute of Jeolgi, but 14:30 May 5 is safely previous month usually?
        # Ipha is usually May 5/6. If Ipha is May 6, then it is Geng-Chen (Sprint month).
        # If Ipha is May 5 10:00, then it is Xin-Si (Summer month).
        # We need accurate Manse for this.
        
    def test_five_rats_hour_logic(self):
        """Test Hour Pillar derivation (Day Stem -> Hour Stem)"""
        # Day: 甲(Gap) -> Hour: Chuk(01:30) -> Should be Yi-Chuk (乙丑)
        # Rule: Gap/Gi day -> Rat hour is Gap-Ja.
        # Gap-Ja -> Yi-Chuk.
        
        day_stem = Stem.objects.get(character='甲')
        hour_branch = Branch.objects.get(character='丑')
        
        hour_stem = calculator.get_hour_stem(day_stem, hour_branch)
        self.assertEqual(hour_stem.character, '乙')

    def test_ten_gods_logic(self):
        """Test Ten Gods derivation"""
        # Day Master: 甲 (Wood +)
        # Target: 丙 (Fire +) -> Wood generates Fire -> Eating God (식신)
        # Target: 庚 (Metal +) -> Metal controls Wood -> 7 Killings (편관)
        
        dm = Stem.objects.get(character='甲') # Wood Yang
        target1 = Stem.objects.get(character='丙') # Fire Yang
        target2 = Stem.objects.get(character='庚') # Metal Yang
        
        god1 = calculator.get_ten_god(dm, target1)
        god2 = calculator.get_ten_god(dm, target2)
        
        self.assertEqual(god1, 'Eating God') # 식신
        self.assertEqual(god2, 'Seven Killings') # 편관

    def test_strength_scoring(self):
        """Test chart strength calculation logic"""
        # Mock a chart
        chart = {
            'month_branch': Branch.objects.get(character='寅'), # Wood (Spring)
            'day_stem': Stem.objects.get(character='甲'), # Wood
            # ... support ...
        }
        # In Spring (寅), Wood (甲) is Strong (得令).
        score = calculator.calculate_strength(chart)
        # Should be > 50 ideally if supported
        pass
