import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import UserProfile
from happy_seed.models import HSClassroom, HSStudent
from seed_quiz.models import SQGamePlayer, SQGameQuestion, SQGameReward, SQGameRoom
from seed_quiz.services.game_core import advance_phase, create_game_room

User = get_user_model()


def _make_teacher(username):
    teacher = User.objects.create_user(
        username=username, password="pw", email=f"{username}@test.com"
    )
    UserProfile.objects.update_or_create(
        user=teacher, defaults={"nickname": username, "role": "school"}
    )
    return teacher


class SeedQuizGameModeTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher("sqg_teacher")
        self.classroom = HSClassroom.objects.create(
            name="실시간 게임반",
            teacher=self.teacher,
            slug=f"sqg-{uuid.uuid4().hex[:6]}",
        )
        self.student1 = HSStudent.objects.create(classroom=self.classroom, name="하나", number=1)
        self.student2 = HSStudent.objects.create(classroom=self.classroom, name="둘", number=2)
        self.teacher_client = Client()
        self.teacher_client.force_login(self.teacher)
        self.student_client_1 = Client()
        self.student_client_2 = Client()

    def _create_room(self, **overrides):
        defaults = {
            "classroom": self.classroom,
            "created_by": self.teacher,
            "title": "씨앗 대결",
            "topic": "orthography",
            "grade": 3,
            "question_mode": "ox",
            "questions_per_player": 1,
            "solve_target_count": 5,
            "create_time_seconds": 300,
            "solve_time_seconds": 300,
            "reward_enabled": True,
        }
        defaults.update(overrides)
        return create_game_room(**defaults)

    def test_teacher_can_create_room_from_view(self):
        url = reverse("seed_quiz:teacher_game_create", kwargs={"classroom_id": self.classroom.id})
        response = self.teacher_client.post(
            url,
            {
                "title": "맞춤법 배틀",
                "topic": "orthography",
                "grade": "3",
                "question_mode": "mixed",
                "questions_per_player": "1",
                "solve_target_count": "4",
                "create_minutes": "5",
                "solve_minutes": "5",
                "reward_enabled": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        room = SQGameRoom.objects.get(classroom=self.classroom)
        self.assertEqual(room.title, "맞춤법 배틀")
        self.assertEqual(room.question_mode, "mixed")
        self.assertTrue(room.reward_enabled)

    @patch("seed_quiz.services.game_core.evaluate_question_quality")
    def test_question_status_turns_pending_question_ready(self, mock_quality):
        mock_quality.return_value = {
            "relevance": 90,
            "clarity": 85,
            "difficulty": 70,
            "overall": 88,
            "approved": True,
            "feedback": "좋은 문제입니다.",
            "fallback_used": False,
        }
        room = self._create_room()
        advance_phase(room, to_status="creating")
        self.student_client_1.post(
            reverse("seed_quiz:student_game_start"),
            {"join_code": room.join_code, "number": "1", "name": "하나"},
        )
        submit_url = reverse("seed_quiz:htmx_student_game_submit_question")
        response = self.student_client_1.post(
            submit_url,
            {
                "question_type": "ox",
                "question_text": "서울은 대한민국의 수도다.",
                "correct_ox": "O",
            },
        )
        self.assertEqual(response.status_code, 200)
        question = SQGameQuestion.objects.get(game=room)
        status_url = reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": question.id})
        response = self.student_client_1.get(status_url)
        self.assertEqual(response.status_code, 200)
        question.refresh_from_db()
        self.assertEqual(question.status, "ready")
        self.assertGreaterEqual(question.base_points, 40)
        self.assertContains(response, "문제가 준비됐어요")

    @patch("seed_quiz.services.game_core.add_seeds")
    @patch("seed_quiz.services.game_core.evaluate_question_quality")
    def test_full_game_flow_finishes_and_creates_rewards(self, mock_quality, mock_add_seeds):
        mock_quality.return_value = {
            "relevance": 90,
            "clarity": 90,
            "difficulty": 75,
            "overall": 86,
            "approved": True,
            "feedback": "사용 가능",
            "fallback_used": False,
        }
        room = self._create_room()

        join_url = reverse("seed_quiz:student_game_start")
        self.student_client_1.post(join_url, {"join_code": room.join_code, "number": "1", "name": "하나"})
        self.student_client_2.post(join_url, {"join_code": room.join_code, "number": "2", "name": "둘"})

        advance_phase(room, to_status="creating")

        submit_url = reverse("seed_quiz:htmx_student_game_submit_question")
        self.student_client_1.post(
            submit_url,
            {"question_type": "ox", "question_text": "지구는 둥글다.", "correct_ox": "O"},
        )
        self.student_client_2.post(
            submit_url,
            {"question_type": "ox", "question_text": "태양은 서쪽에서 뜬다.", "correct_ox": "X"},
        )

        q1 = SQGameQuestion.objects.get(author__student=self.student1)
        q2 = SQGameQuestion.objects.get(author__student=self.student2)
        self.student_client_1.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q1.id}))
        self.student_client_2.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q2.id}))

        advance_phase(room, to_status="playing")

        answer1 = reverse("seed_quiz:htmx_student_game_answer", kwargs={"question_id": q2.id})
        answer2 = reverse("seed_quiz:htmx_student_game_answer", kwargs={"question_id": q1.id})
        response1 = self.student_client_1.post(answer1, {"selected_index": "1", "time_taken_ms": "1000"})
        response2 = self.student_client_2.post(answer2, {"selected_index": "0", "time_taken_ms": "1500"})

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)

        room.refresh_from_db()
        self.assertEqual(room.status, "finished")

        players = list(SQGamePlayer.objects.filter(game=room).order_by("rank"))
        self.assertEqual(len(players), 2)
        self.assertEqual(players[0].rank, 1)
        self.assertGreater(players[0].total_score, 0)
        self.assertEqual(SQGameReward.objects.filter(game=room).count(), 2)
        self.assertEqual(mock_add_seeds.call_count, 2)
