from django.test import TestCase
from datetime import datetime
import pytz
from fortune.libs import manse

class ManseEngineTests(TestCase):
    def test_solar_term_accuracy(self):
        """
        Verify precise Lichun (Start of Spring) time for 2024.
        2024 Lichun is Feb 4, approx 16:27 KST.
        """
        # We expect the engine to return a datetime close to this
        lichun_2024 = manse.get_solar_term_date(2024, 'Lichun') # 입춘
        
        # Checking if it's within a reasonable margin or exact minute if possible
        # Required: 2024-02-04
        self.assertEqual(lichun_2024.year, 2024)
        self.assertEqual(lichun_2024.month, 2)
        self.assertEqual(lichun_2024.day, 4)
        
    def test_solar_term_list(self):
        """Ensure all 24 terms can be retrieved"""
        terms = manse.get_all_solar_terms(2024)
        self.assertEqual(len(terms), 24)
        self.assertIn('Lichun', terms)
        self.assertIn('Dongji', terms)

    def test_equation_of_time_correction(self):
        """
        Test true solar time calculation.
        Seoul is ~127.0 deg East. KST is 135 deg.
        Difference is 8 deg. 8 * 4 min = 32 mins delay relative to standard time.
        Plus EOT variation.
        """
        # Date: 2024-02-04 12:00:00 KST
        standard_time = datetime(2024, 2, 4, 12, 0, 0, tzinfo=pytz.timezone('Asia/Seoul'))
        
        # Just longitude correction: 12:00 - 32m = 11:28 approx.
        # This test ensures the function doesn't crash and returns a different time
        true_solar = manse.get_apparent_solar_time(standard_time, 127.0)
        
        diff = (standard_time - true_solar).total_seconds() / 60
        # Expect roughly 30-35 mins difference
        self.assertTrue(25 < diff < 40, f"Difference {diff} minutes is out of expected range (approx 32)")

    def test_lunar_to_solar(self):
        """
        Verify Lunar to Solar conversion using standard reference
        1990 Lunar 1.1 -> 1990 Solar 1.27
        """
        solar_date = manse.lunar_to_solar(1990, 1, 1, False) # Non-leap
        self.assertEqual(solar_date.year, 1990)
        self.assertEqual(solar_date.month, 1)
        self.assertEqual(solar_date.day, 27)
