import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.models import UserProfile
from happy_seed.models import HSClassroom, HSStudent
from seed_quiz.models import SQGameAnswer, SQGamePlayer, SQGameQuestion, SQGameReward, SQGameRoom
from seed_quiz.services.game_core import (
    advance_phase,
    assigned_questions_for_player,
    create_game_room,
    get_next_question_for_player,
)

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
        self.student3 = HSStudent.objects.create(classroom=self.classroom, name="셋", number=3)
        self.teacher_client = Client()
        self.teacher_client.force_login(self.teacher)
        self.student_client_1 = Client()
        self.student_client_2 = Client()
        self.student_client_3 = Client()

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

    def _join_student(self, client, student, *, name=None):
        return client.post(
            reverse("seed_quiz:student_game_start"),
            {
                "join_code": self.room.join_code,
                "number": str(student.number),
                "name": name or student.name,
            },
        )

    def _submit_question(self, client, *, request_id=None, **overrides):
        payload = {
            "request_id": request_id or str(uuid.uuid4()),
            "question_type": "ox",
            "question_text": "서울은 대한민국의 수도다.",
            "correct_ox": "O",
        }
        payload.update(overrides)
        return client.post(reverse("seed_quiz:htmx_student_game_submit_question"), payload)

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
        room = SQGameRoom.objects.get(classroom=self.classroom)
        room_url = reverse("seed_quiz:teacher_game_room", kwargs={"classroom_id": self.classroom.id, "room_id": room.id})
        self.assertRedirects(response, room_url)
        self.assertEqual(room.title, "맞춤법 배틀")
        self.assertEqual(room.question_mode, "mixed")
        self.assertTrue(room.reward_enabled)

    def test_teacher_create_invalid_grade_returns_form_without_500(self):
        url = reverse("seed_quiz:teacher_game_create", kwargs={"classroom_id": self.classroom.id})
        response = self.teacher_client.post(
            url,
            {
                "title": "안정화 게임",
                "topic": "orthography",
                "grade": "abc",
                "question_mode": "mixed",
                "questions_per_player": "1",
                "solve_target_count": "4",
                "create_minutes": "5",
                "solve_minutes": "5",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학년을 다시 확인해 주세요.")
        self.assertFalse(SQGameRoom.objects.filter(classroom=self.classroom).exists())

    def test_teacher_create_out_of_range_setting_returns_form_without_500(self):
        url = reverse("seed_quiz:teacher_game_create", kwargs={"classroom_id": self.classroom.id})
        response = self.teacher_client.post(
            url,
            {
                "title": "안정화 게임",
                "topic": "orthography",
                "grade": "3",
                "question_mode": "mixed",
                "questions_per_player": "9",
                "solve_target_count": "4",
                "create_minutes": "5",
                "solve_minutes": "5",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "출제 수를 다시 확인해 주세요.")
        self.assertFalse(SQGameRoom.objects.filter(classroom=self.classroom).exists())

    def test_student_can_join_game_and_load_shell(self):
        self.room = self._create_room()
        response = self._join_student(self.student_client_1, self.student1)
        shell_url = reverse("seed_quiz:student_game_shell")
        self.assertRedirects(response, shell_url)
        shell = self.student_client_1.get(shell_url)
        self.assertEqual(shell.status_code, 200)
        self.assertContains(shell, "게임을 불러오는 중입니다.")

    def test_student_join_invalid_name_redirects_with_error(self):
        self.room = self._create_room()
        response = self.student_client_1.post(
            reverse("seed_quiz:student_game_start"),
            {
                "join_code": self.room.join_code,
                "number": str(self.student1.number),
                "name": "없는이름",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("seed_quiz:student_game_join_code", kwargs={"join_code": self.room.join_code}),
        )
        follow = self.student_client_1.get(response.url)
        self.assertContains(follow, "번호와 이름을 다시 확인해 주세요.")

    @patch("seed_quiz.services.game_core.evaluate_question_quality")
    def test_same_request_id_only_creates_one_question(self, mock_quality):
        mock_quality.return_value = {
            "relevance": 88,
            "clarity": 82,
            "difficulty": 70,
            "overall": 84,
            "approved": True,
            "feedback": "사용 가능",
            "fallback_used": False,
        }
        self.room = self._create_room()
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)

        request_id = str(uuid.uuid4())
        response1 = self._submit_question(self.student_client_1, request_id=request_id)
        response2 = self._submit_question(self.student_client_1, request_id=request_id)

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(SQGameQuestion.objects.filter(game=self.room).count(), 1)
        question = SQGameQuestion.objects.get(game=self.room)
        self.assertEqual(str(question.request_id), request_id)

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

    @patch("seed_quiz.services.game_core.evaluate_question_quality", side_effect=RuntimeError("deepseek timeout"))
    def test_ai_failure_moves_question_to_needs_review(self, mock_quality):
        self.room = self._create_room()
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)

        submit_response = self._submit_question(self.student_client_1)
        self.assertEqual(submit_response.status_code, 200)
        question = SQGameQuestion.objects.get(game=self.room)

        response = self.student_client_1.get(
            reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": question.id})
        )

        question.refresh_from_db()
        self.assertEqual(question.status, "needs_review")
        self.assertEqual(question.base_points, 0)
        self.assertContains(response, "선생님 확인 중")
        self.assertTrue(mock_quality.called)

    def test_generate_choices_with_broken_text_returns_partial_error(self):
        self.room = self._create_room(question_mode="mixed")
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)

        response = self.student_client_1.post(
            reverse("seed_quiz:htmx_student_game_generate_choices"),
            {
                "question_text": "깨진\ufffd문자 문제",
                "answer_text": "정답",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "문제 글자를 다시 확인해 주세요.")

    def test_submit_question_with_broken_text_returns_same_form(self):
        self.room = self._create_room(question_mode="mixed")
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)

        response = self.student_client_1.post(
            reverse("seed_quiz:htmx_student_game_submit_question"),
            {
                "request_id": str(uuid.uuid4()),
                "question_type": "mc4",
                "question_text": "깨진\ufffd문자 문제",
                "answer_text": "정답",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "문제 글자를 다시 확인해 주세요.")
        self.assertEqual(SQGameQuestion.objects.filter(game=self.room).count(), 0)

    def test_submit_question_with_invalid_correct_index_returns_same_form(self):
        self.room = self._create_room(question_mode="mixed")
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)

        response = self.student_client_1.post(
            reverse("seed_quiz:htmx_student_game_submit_question"),
            {
                "request_id": str(uuid.uuid4()),
                "question_type": "mc4",
                "question_text": "우리나라 수도는 어디일까요?",
                "answer_text": "서울",
                "choice_0": "서울",
                "choice_1": "부산",
                "choice_2": "인천",
                "choice_3": "대전",
                "correct_index": "9",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "정답 위치를 다시 확인해 주세요.")
        self.assertEqual(SQGameQuestion.objects.filter(game=self.room).count(), 0)

    def test_submit_question_with_duplicate_choices_returns_same_form(self):
        self.room = self._create_room(question_mode="mixed")
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)

        response = self.student_client_1.post(
            reverse("seed_quiz:htmx_student_game_submit_question"),
            {
                "request_id": str(uuid.uuid4()),
                "question_type": "mc4",
                "question_text": "우리나라 수도는 어디일까요?",
                "answer_text": "서울",
                "choice_0": "서울",
                "choice_1": "서울",
                "choice_2": "인천",
                "choice_3": "대전",
                "correct_index": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "보기는 서로 다르게 적어 주세요.")
        self.assertEqual(SQGameQuestion.objects.filter(game=self.room).count(), 0)

    def test_teacher_can_approve_needs_review_question_with_default_points(self):
        self.room = self._create_room()
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)
        player = SQGamePlayer.objects.get(game=self.room, student=self.student1)
        question = SQGameQuestion.objects.create(
            game=self.room,
            author=player,
            question_type="ox",
            question_text="승인 대기 문제",
            answer_text="O",
            choices=["O", "X"],
            correct_index=0,
            status="needs_review",
            ai_feedback="선생님 확인 필요",
        )

        response = self.teacher_client.post(
            reverse(
                "seed_quiz:htmx_teacher_game_review",
                kwargs={
                    "classroom_id": self.classroom.id,
                    "room_id": self.room.id,
                    "question_id": question.id,
                },
            ),
            {"action": "approve"},
        )

        question.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(question.status, "ready")
        self.assertEqual(question.base_points, 20)

    def test_teacher_can_reject_needs_review_question(self):
        self.room = self._create_room()
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)
        player = SQGamePlayer.objects.get(game=self.room, student=self.student1)
        question = SQGameQuestion.objects.create(
            game=self.room,
            author=player,
            question_type="ox",
            question_text="제외 대기 문제",
            answer_text="O",
            choices=["O", "X"],
            correct_index=0,
            status="needs_review",
            ai_feedback="선생님 확인 필요",
        )

        response = self.teacher_client.post(
            reverse(
                "seed_quiz:htmx_teacher_game_review",
                kwargs={
                    "classroom_id": self.classroom.id,
                    "room_id": self.room.id,
                    "question_id": question.id,
                },
            ),
            {"action": "reject"},
        )

        question.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(question.status, "rejected")
        self.assertEqual(question.base_points, 0)

    def test_teacher_review_invalid_action_returns_panel_error(self):
        self.room = self._create_room()
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)
        player = SQGamePlayer.objects.get(game=self.room, student=self.student1)
        question = SQGameQuestion.objects.create(
            game=self.room,
            author=player,
            question_type="ox",
            question_text="검토 액션 테스트",
            answer_text="O",
            choices=["O", "X"],
            correct_index=0,
            status="needs_review",
        )

        response = self.teacher_client.post(
            reverse(
                "seed_quiz:htmx_teacher_game_review",
                kwargs={
                    "classroom_id": self.classroom.id,
                    "room_id": self.room.id,
                    "question_id": question.id,
                },
            ),
            {"action": "bad-action"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "검토 처리에 실패했습니다.")
        question.refresh_from_db()
        self.assertEqual(question.status, "needs_review")

    def test_needs_review_blocks_start_playing(self):
        self.room = self._create_room()
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)
        player = SQGamePlayer.objects.get(game=self.room, student=self.student1)
        SQGameQuestion.objects.create(
            game=self.room,
            author=player,
            question_type="ox",
            question_text="검토 대기 문제",
            answer_text="O",
            choices=["O", "X"],
            correct_index=0,
            status="needs_review",
            ai_feedback="검토 필요",
        )

        response = self.teacher_client.post(
            reverse(
                "seed_quiz:htmx_teacher_game_advance",
                kwargs={"classroom_id": self.classroom.id, "room_id": self.room.id},
            ),
            {"to_status": "playing"},
        )

        self.room.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.room.status, "creating")
        self.assertContains(response, "검토 대기를 먼저 처리해 주세요.")

    @patch("seed_quiz.services.game_core.evaluate_question_quality")
    def test_player_cannot_answer_question_out_of_turn(self, mock_quality):
        mock_quality.return_value = {
            "relevance": 90,
            "clarity": 88,
            "difficulty": 70,
            "overall": 85,
            "approved": True,
            "feedback": "사용 가능",
            "fallback_used": False,
        }
        self.room = self._create_room(solve_target_count=2)
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)
        self._join_student(self.student_client_2, self.student2)
        self._join_student(self.student_client_3, self.student3)

        self._submit_question(self.student_client_1, question_text="지구는 둥글다.", correct_ox="O")
        self._submit_question(self.student_client_2, question_text="바다는 육지다.", correct_ox="X")
        self._submit_question(self.student_client_3, question_text="봄 다음은 여름이다.", correct_ox="O")

        q1 = SQGameQuestion.objects.get(author__student=self.student1)
        q2 = SQGameQuestion.objects.get(author__student=self.student2)
        q3 = SQGameQuestion.objects.get(author__student=self.student3)
        self.student_client_1.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q1.id}))
        self.student_client_2.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q2.id}))
        self.student_client_3.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q3.id}))

        advance_phase(self.room, to_status="playing")

        player = SQGamePlayer.objects.get(game=self.room, student=self.student1)
        assigned = assigned_questions_for_player(player)
        next_question = get_next_question_for_player(player)
        wrong_question = next(question for question in assigned if question.id != next_question.id)

        response = self.student_client_1.post(
            reverse("seed_quiz:htmx_student_game_answer", kwargs={"question_id": wrong_question.id}),
            {"selected_index": "0", "time_taken_ms": "1000"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SQGameAnswer.objects.filter(player=player).count(), 0)
        self.assertContains(response, "지금 문제부터 풀어 주세요.")
        self.assertContains(response, next_question.question_text)

    @patch("seed_quiz.services.game_core.evaluate_question_quality")
    def test_ox_answer_rejects_out_of_range_index(self, mock_quality):
        mock_quality.return_value = {
            "relevance": 90,
            "clarity": 88,
            "difficulty": 70,
            "overall": 85,
            "approved": True,
            "feedback": "사용 가능",
            "fallback_used": False,
        }
        self.room = self._create_room()
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)
        self._join_student(self.student_client_2, self.student2)

        self._submit_question(self.student_client_1, question_text="지구는 둥글다.", correct_ox="O")
        self._submit_question(self.student_client_2, question_text="바다는 육지다.", correct_ox="X")

        q1 = SQGameQuestion.objects.get(author__student=self.student1)
        q2 = SQGameQuestion.objects.get(author__student=self.student2)
        self.student_client_1.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q1.id}))
        self.student_client_2.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q2.id}))

        advance_phase(self.room, to_status="playing")

        response = self.student_client_1.post(
            reverse("seed_quiz:htmx_student_game_answer", kwargs={"question_id": q2.id}),
            {"selected_index": "2", "time_taken_ms": "1000"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SQGameAnswer.objects.filter(player__game=self.room).count(), 0)
        self.assertContains(response, "답을 다시 골라 주세요.")
        self.assertContains(response, q2.question_text)

    @patch("seed_quiz.services.game_core.evaluate_question_quality")
    def test_duplicate_answer_returns_existing_result(self, mock_quality):
        mock_quality.return_value = {
            "relevance": 90,
            "clarity": 88,
            "difficulty": 70,
            "overall": 85,
            "approved": True,
            "feedback": "사용 가능",
            "fallback_used": False,
        }
        self.room = self._create_room()
        advance_phase(self.room, to_status="creating")
        self._join_student(self.student_client_1, self.student1)
        self._join_student(self.student_client_2, self.student2)

        self._submit_question(self.student_client_1, question_text="지구는 둥글다.", correct_ox="O")
        self._submit_question(self.student_client_2, question_text="바다는 육지다.", correct_ox="X")

        q1 = SQGameQuestion.objects.get(author__student=self.student1)
        q2 = SQGameQuestion.objects.get(author__student=self.student2)
        self.student_client_1.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q1.id}))
        self.student_client_2.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q2.id}))

        advance_phase(self.room, to_status="playing")

        answer_url = reverse("seed_quiz:htmx_student_game_answer", kwargs={"question_id": q2.id})
        response1 = self.student_client_1.post(answer_url, {"selected_index": "1", "time_taken_ms": "1000"})
        response2 = self.student_client_1.post(answer_url, {"selected_index": "1", "time_taken_ms": "1000"})

        player = SQGamePlayer.objects.get(game=self.room, student=self.student1)
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(SQGameAnswer.objects.filter(player=player, question=q2).count(), 1)
        self.assertContains(response2, "정답")

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
        self.room = self._create_room()

        join_url = reverse("seed_quiz:student_game_start")
        self.student_client_1.post(join_url, {"join_code": self.room.join_code, "number": "1", "name": "하나"})
        self.student_client_2.post(join_url, {"join_code": self.room.join_code, "number": "2", "name": "둘"})

        advance_phase(self.room, to_status="creating")

        submit_url = reverse("seed_quiz:htmx_student_game_submit_question")
        self.student_client_1.post(
            submit_url,
            {"request_id": str(uuid.uuid4()), "question_type": "ox", "question_text": "지구는 둥글다.", "correct_ox": "O"},
        )
        self.student_client_2.post(
            submit_url,
            {"request_id": str(uuid.uuid4()), "question_type": "ox", "question_text": "태양은 서쪽에서 뜬다.", "correct_ox": "X"},
        )

        q1 = SQGameQuestion.objects.get(author__student=self.student1)
        q2 = SQGameQuestion.objects.get(author__student=self.student2)
        self.student_client_1.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q1.id}))
        self.student_client_2.get(reverse("seed_quiz:htmx_student_game_question_status", kwargs={"question_id": q2.id}))

        advance_phase(self.room, to_status="playing")

        answer1 = reverse("seed_quiz:htmx_student_game_answer", kwargs={"question_id": q2.id})
        answer2 = reverse("seed_quiz:htmx_student_game_answer", kwargs={"question_id": q1.id})
        response1 = self.student_client_1.post(answer1, {"selected_index": "1", "time_taken_ms": "1000"})
        response2 = self.student_client_2.post(answer2, {"selected_index": "0", "time_taken_ms": "1500"})

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)

        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "finished")

        players = list(SQGamePlayer.objects.filter(game=self.room).order_by("rank"))
        self.assertEqual(len(players), 2)
        self.assertEqual(players[0].rank, 1)
        self.assertGreater(players[0].total_score, 0)
        self.assertEqual(SQGameReward.objects.filter(game=self.room).count(), 2)
        self.assertEqual(mock_add_seeds.call_count, 2)
