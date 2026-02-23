from django.test import SimpleTestCase

from seed_quiz.services.validator import normalize_and_check, validate_quiz_payload


def _make_payload(overrides=None):
    """유효한 기본 payload 생성."""
    items = [
        {
            "question_text": f"문제 {i}번 입니다",
            "choices": ["선택지1", "선택지2", "선택지3", "선택지4"],
            "correct_index": 0,
            "explanation": "해설입니다",
            "difficulty": "medium",
        }
        for i in range(1, 4)
    ]
    payload = {"items": items}
    if overrides:
        payload.update(overrides)
    return payload


class ValidatorNormalizeTest(SimpleTestCase):
    def test_strips_whitespace(self):
        result = normalize_and_check("  hello  ")
        self.assertEqual(result, "hello")

    def test_removes_html_tags(self):
        result = normalize_and_check("<b>bold</b>")
        self.assertEqual(result, "bold")

    def test_raises_on_broken_char(self):
        with self.assertRaises(ValueError):
            normalize_and_check("hello\ufffdworld")

    def test_removes_control_chars(self):
        result = normalize_and_check("hello\x00world")
        self.assertEqual(result, "helloworld")


class ValidateQuizPayloadTest(SimpleTestCase):
    def test_valid_payload(self):
        ok, errors = validate_quiz_payload(_make_payload())
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_too_few_items(self):
        payload = {"items": []}
        ok, errors = validate_quiz_payload(payload)
        self.assertFalse(ok)
        self.assertIn("item_count_too_small", errors)

    def test_too_many_items(self):
        base_item = _make_payload()["items"][0]
        payload = {"items": [base_item for _ in range(201)]}
        ok, errors = validate_quiz_payload(payload)
        self.assertFalse(ok)
        self.assertIn("item_count_too_large", errors)

    def test_duplicate_choice(self):
        payload = _make_payload()
        payload["items"][0]["choices"] = ["같은값", "같은값", "선택지3", "선택지4"]
        ok, errors = validate_quiz_payload(payload)
        self.assertFalse(ok)
        self.assertIn("q1_duplicate_choice", errors)

    def test_invalid_correct_index(self):
        payload = _make_payload()
        payload["items"][1]["correct_index"] = 4
        ok, errors = validate_quiz_payload(payload)
        self.assertFalse(ok)
        self.assertIn("q2_invalid_correct_index", errors)

    def test_correct_index_minus_one(self):
        payload = _make_payload()
        payload["items"][0]["correct_index"] = -1
        ok, errors = validate_quiz_payload(payload)
        self.assertFalse(ok)
        self.assertIn("q1_invalid_correct_index", errors)

    def test_choices_not_4(self):
        payload = _make_payload()
        payload["items"][2]["choices"] = ["A", "B", "C"]
        ok, errors = validate_quiz_payload(payload)
        self.assertFalse(ok)
        self.assertIn("q3_choices_not_4", errors)

    def test_empty_choice(self):
        payload = _make_payload()
        payload["items"][0]["choices"] = ["", "선택지2", "선택지3", "선택지4"]
        ok, errors = validate_quiz_payload(payload)
        self.assertFalse(ok)
        self.assertIn("q1_empty_choice", errors)

    def test_question_too_long(self):
        payload = _make_payload()
        payload["items"][0]["question_text"] = "가" * 121
        ok, errors = validate_quiz_payload(payload)
        self.assertFalse(ok)
        self.assertIn("q1_question_length", errors)
