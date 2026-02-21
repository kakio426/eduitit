import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from happy_seed.models import HSClassroom
from seed_quiz.models import SQQuizSet

User = get_user_model()


def _make_teacher(username):
    teacher = User.objects.create_user(
        username=username, password="pw", email=f"{username}@test.com"
    )
    UserProfile.objects.update_or_create(
        user=teacher, defaults={"nickname": username, "role": "school"}
    )
    return teacher

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


class TeacherFlowTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher("tf_teacher")
        self.other_teacher = _make_teacher("tf_other")
        self.classroom = HSClassroom.objects.create(
            name="흐름 테스트반",
            teacher=self.teacher,
            slug=f"flow-{uuid.uuid4().hex[:6]}",
        )
        self.client = Client()
        self.client.force_login(self.teacher)

    def test_dashboard_returns_200(self):
        url = reverse(
            "seed_quiz:teacher_dashboard",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_other_teacher_forbidden(self):
        other_client = Client()
        other_client.force_login(self.other_teacher)
        url = reverse(
            "seed_quiz:teacher_dashboard",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = other_client.get(url)
        self.assertEqual(resp.status_code, 404)

    @patch("seed_quiz.services.generation._call_ai")
    def test_generate_returns_preview(self, mock_ai):
        mock_ai.return_value = VALID_AI_RESPONSE
        url = reverse(
            "seed_quiz:htmx_generate",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(url, {"preset_type": "general", "grade": "3"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "우리나라 수도는?")

    @patch("seed_quiz.services.generation._call_ai")
    def test_publish_changes_status(self, mock_ai):
        mock_ai.return_value = VALID_AI_RESPONSE
        # 생성
        gen_url = reverse(
            "seed_quiz:htmx_generate",
            kwargs={"classroom_id": self.classroom.id},
        )
        self.client.post(gen_url, {"preset_type": "general", "grade": "3"})
        quiz_set = SQQuizSet.objects.filter(classroom=self.classroom).first()
        self.assertIsNotNone(quiz_set)

        # 배포
        pub_url = reverse(
            "seed_quiz:htmx_publish",
            kwargs={
                "classroom_id": self.classroom.id,
                "set_id": quiz_set.id,
            },
        )
        resp = self.client.post(pub_url)
        self.assertEqual(resp.status_code, 200)
        quiz_set.refresh_from_db()
        self.assertEqual(quiz_set.status, "published")

    @patch("seed_quiz.services.generation._call_ai")
    def test_publish_closes_existing_published(self, mock_ai):
        mock_ai.return_value = VALID_AI_RESPONSE
        gen_url = reverse(
            "seed_quiz:htmx_generate",
            kwargs={"classroom_id": self.classroom.id},
        )

        # 첫 번째 생성
        self.client.post(gen_url, {"preset_type": "general", "grade": "3"})
        qs1 = SQQuizSet.objects.filter(classroom=self.classroom).order_by("created_at").first()
        self.assertIsNotNone(qs1)
        pub_url = reverse(
            "seed_quiz:htmx_publish",
            kwargs={"classroom_id": self.classroom.id, "set_id": qs1.id},
        )
        self.client.post(pub_url)
        qs1.refresh_from_db()
        self.assertEqual(qs1.status, "published")

        # 두 번째 생성 (다시 생성하면 같은 draft 세트 재사용)
        self.client.post(gen_url, {"preset_type": "general", "grade": "3"})
        # draft가 다시 생겼는지 확인 (qs1이 published → 새 draft)
        qs2 = SQQuizSet.objects.filter(classroom=self.classroom, status="draft").first()
        self.assertIsNotNone(qs2)
        pub_url2 = reverse(
            "seed_quiz:htmx_publish",
            kwargs={"classroom_id": self.classroom.id, "set_id": qs2.id},
        )
        self.client.post(pub_url2)
        qs1.refresh_from_db()
        qs2.refresh_from_db()
        self.assertEqual(qs1.status, "closed")
        self.assertEqual(qs2.status, "published")
