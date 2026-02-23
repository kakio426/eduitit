import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import UserProfile
from happy_seed.models import HSClassroom
from seed_quiz.models import SQGenerationLog, SQQuizSet
from seed_quiz.services.generation import generate_and_save_draft

User = get_user_model()


def _make_teacher(username):
    teacher = User.objects.create_user(
        username=username, password="pw", email=f"{username}@test.com"
    )
    UserProfile.objects.update_or_create(
        user=teacher, defaults={"nickname": username, "role": "school"}
    )
    return teacher


def make_classroom(teacher):
    return HSClassroom.objects.create(
        name="3학년 2반",
        school_name="테스트초",
        teacher=teacher,
        slug=f"gen-test-{uuid.uuid4().hex[:6]}",
    )


VALID_AI_RESPONSE = {
    "items": [
        {
            "question_text": "우리나라 수도는?",
            "choices": ["부산", "서울", "대구", "인천"],
            "correct_index": 1,
            "explanation": "서울입니다.",
            "difficulty": "easy",
        },
        {
            "question_text": "1+1은?",
            "choices": ["1", "2", "3", "4"],
            "correct_index": 1,
            "explanation": "2입니다.",
            "difficulty": "easy",
        },
        {
            "question_text": "태양은 어디서 뜨나요?",
            "choices": ["서쪽", "남쪽", "동쪽", "북쪽"],
            "correct_index": 2,
            "explanation": "동쪽에서 뜹니다.",
            "difficulty": "easy",
        },
    ]
}


class GenerationTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher("gen_teacher")
        self.classroom = make_classroom(self.teacher)

    @patch("seed_quiz.services.generation._call_ai")
    def test_ai_success_creates_draft(self, mock_call_ai):
        mock_call_ai.return_value = VALID_AI_RESPONSE
        quiz_set = generate_and_save_draft(self.classroom, "orthography", 3, self.teacher)

        self.assertEqual(quiz_set.status, "draft")
        self.assertEqual(quiz_set.source, "ai")
        self.assertEqual(quiz_set.items.count(), 3)

    @patch("seed_quiz.services.generation._call_ai")
    def test_ai_timeout_falls_back_to_fallback(self, mock_call_ai):
        mock_call_ai.side_effect = Exception("timeout")
        quiz_set = generate_and_save_draft(self.classroom, "orthography", 3, self.teacher)

        self.assertEqual(quiz_set.status, "draft")
        self.assertEqual(quiz_set.source, "fallback")
        self.assertEqual(quiz_set.items.count(), 3)
        # 로그에 FALLBACK_USED가 기록되어야 함
        self.assertTrue(
            SQGenerationLog.objects.filter(quiz_set=quiz_set, code="FALLBACK_USED").exists()
        )

    @patch("seed_quiz.services.generation._call_ai")
    @patch("seed_quiz.services.generation.load_fallback_bank")
    def test_both_fail_raises_runtime_error(self, mock_fallback, mock_call_ai):
        mock_call_ai.side_effect = Exception("AI down")
        mock_fallback.side_effect = FileNotFoundError("no fallback")

        with self.assertRaises(RuntimeError):
            generate_and_save_draft(self.classroom, "orthography", 3, self.teacher)

        # atomic 밖에서 status=failed 저장되므로 DB에 반영됨
        quiz_set = SQQuizSet.objects.filter(classroom=self.classroom).first()
        self.assertIsNotNone(quiz_set)
        self.assertEqual(quiz_set.status, "failed")
        # FALLBACK_FAILED 로그 확인
        self.assertTrue(
            SQGenerationLog.objects.filter(code="FALLBACK_FAILED").exists()
        )

    @patch("seed_quiz.services.generation._call_ai")
    def test_regeneration_creates_new_draft_set(self, mock_call_ai):
        mock_call_ai.return_value = VALID_AI_RESPONSE
        # 첫 번째 생성
        qs1 = generate_and_save_draft(self.classroom, "orthography", 3, self.teacher)
        self.assertEqual(qs1.items.count(), 3)

        # 두 번째 생성
        qs2 = generate_and_save_draft(self.classroom, "orthography", 3, self.teacher)
        self.assertNotEqual(qs1.id, qs2.id)  # 새 draft 세트로 보존
        self.assertEqual(qs2.items.count(), 3)
        self.assertEqual(
            SQQuizSet.objects.filter(classroom=self.classroom, status="draft").count(),
            2,
        )
