from django.test import TestCase

from portfolio.models import Achievement, LectureProgram


class PortfolioFieldLimitTests(TestCase):
    def test_achievement_image_path_max_length_is_extended(self):
        image_field = Achievement._meta.get_field("image")
        self.assertEqual(image_field.max_length, 500)

    def test_program_thumbnail_path_max_length_is_extended(self):
        thumbnail_field = LectureProgram._meta.get_field("thumbnail")
        self.assertEqual(thumbnail_field.max_length, 500)
