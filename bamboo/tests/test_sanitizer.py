from django.test import SimpleTestCase

from bamboo.utils.comments import sanitize_comment_body
from bamboo.utils.sanitizer import MASK_TOKEN, sanitize_input
from bamboo.utils.safety import SAFE_EXPRESSION_TOKEN


class BambooSanitizerTest(SimpleTestCase):
    def test_masks_teacher_school_class_region_and_contact(self):
        result = sanitize_input(
            "김철수 선생님이 어제 5학년 3반에서 서울새싹초등학교 학부모에게 010-1234-5678로 연락했다."
        )

        self.assertIn(MASK_TOKEN, result.masked_text)
        self.assertNotIn("김철수", result.masked_text)
        self.assertNotIn("서울새싹초등학교", result.masked_text)
        self.assertNotIn("5학년 3반", result.masked_text)
        self.assertNotIn("010-1234-5678", result.masked_text)
        self.assertIn("김철수 선생님이", result.redacted_values)

    def test_keeps_complaint_tone_without_raw_identity(self):
        result = sanitize_input("관리자가 내 공을 빼앗아 가서 진짜 욕하고 싶다.")

        self.assertIn("욕하고 싶다", result.masked_text)
        self.assertEqual((), result.redacted_values)

    def test_comment_blocks_identifiers(self):
        result = sanitize_comment_body("서울새싹초등학교 김철수 선생님 얘기 같네요.")

        self.assertFalse(result.is_valid)
        self.assertIn("identifier", result.reasons)

    def test_story_input_masks_strong_profanity_and_adult_expression(self):
        result = sanitize_input("씨발 야동 같은 농담을 해서 너무 불쾌했다.")

        self.assertIn(SAFE_EXPRESSION_TOKEN, result.masked_text)
        self.assertNotIn("씨발", result.masked_text)
        self.assertNotIn("야동", result.masked_text)

    def test_comment_blocks_strong_profanity(self):
        result = sanitize_comment_body("씨발 이거 진짜 웃기네")

        self.assertFalse(result.is_valid)
        self.assertIn("direct_insult", result.reasons)
