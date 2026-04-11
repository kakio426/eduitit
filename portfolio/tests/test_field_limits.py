from django.test import TestCase

from portfolio.models import Achievement, AchievementPhoto, LectureProgram


class PortfolioFieldLimitTests(TestCase):
    def test_achievement_image_path_max_length_is_extended(self):
        image_field = Achievement._meta.get_field("image")
        self.assertEqual(image_field.max_length, 500)

    def test_achievement_image_caption_limit_matches_ui_contract(self):
        caption_field = Achievement._meta.get_field("image_caption")
        self.assertEqual(caption_field.max_length, 200)

    def test_program_thumbnail_path_max_length_is_extended(self):
        thumbnail_field = LectureProgram._meta.get_field("thumbnail")
        self.assertEqual(thumbnail_field.max_length, 500)

    def test_achievement_photo_image_path_max_length_is_extended(self):
        image_field = AchievementPhoto._meta.get_field("image")
        self.assertEqual(image_field.max_length, 500)
