import uuid

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from happy_seed.models import HSClassroom, HSGuardianConsent, HSStudent
from seed_quiz.models import SQAttempt, SQQuizItem, SQQuizSet

User = get_user_model()


def _make_teacher(username):
    teacher = User.objects.create_user(
        username=username, password="pw", email=f"{username}@test.com"
    )
    UserProfile.objects.update_or_create(
        user=teacher, defaults={"nickname": username, "role": "school"}
    )
    return teacher


def _setup_published_quiz(teacher, classroom):
    qs = SQQuizSet.objects.create(
        classroom=classroom,
        target_date=timezone.localdate(),
        preset_type="general",
        grade=3,
        title="학생 흐름 테스트",
        status="published",
        created_by=teacher,
    )
    for i in range(1, 4):
        SQQuizItem.objects.create(
            quiz_set=qs,
            order_no=i,
            question_text=f"문제 {i}번",
            choices=["A", "B", "C", "D"],
            correct_index=0,
        )
    return qs


class StudentFlowTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher("sf_teacher")
        self.slug = f"sf-{uuid.uuid4().hex[:6]}"
        self.classroom = HSClassroom.objects.create(
            name="학생흐름반",
            teacher=self.teacher,
            slug=self.slug,
        )
        self.quiz_set = _setup_published_quiz(self.teacher, self.classroom)
        self.student = HSStudent.objects.create(
            classroom=self.classroom, name="홍길동", number=7
        )
        self.client = Client()

    def test_gate_no_quiz_shows_waiting(self):
        # 퀴즈 없는 반 (다른 반 테스트)
        other_classroom = HSClassroom.objects.create(
            name="다른반", teacher=self.teacher, slug="other-" + uuid.uuid4().hex[:6]
        )
        url = reverse("seed_quiz:student_gate", kwargs={"class_slug": other_classroom.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "아직 준비중")

    def test_gate_with_quiz_shows_form(self):
        url = reverse("seed_quiz:student_gate", kwargs={"class_slug": self.slug})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "이름")

    def test_invalid_student_redirects_with_error(self):
        url = reverse("seed_quiz:student_start", kwargs={"class_slug": self.slug})
        resp = self.client.post(url, {"number": "99", "name": "없는학생"})
        self.assertEqual(resp.status_code, 302)
        # 세션에 에러 저장 확인
        self.assertIn("sq_gate_error", self.client.session)

    def test_valid_student_creates_attempt_and_session(self):
        url = reverse("seed_quiz:student_start", kwargs={"class_slug": self.slug})
        resp = self.client.post(url, {"number": "7", "name": "홍길동"})
        self.assertEqual(resp.status_code, 302)
        # attempt 생성 확인
        self.assertTrue(SQAttempt.objects.filter(student=self.student).exists())
        # 세션 설정 확인
        session = self.client.session
        self.assertIn("sq_attempt_id", session)

    def test_three_answers_trigger_grading(self):
        # 학생 진입
        start_url = reverse("seed_quiz:student_start", kwargs={"class_slug": self.slug})
        self.client.post(start_url, {"number": "7", "name": "홍길동"})

        # 3문항 순서대로 답변
        answer_url = reverse("seed_quiz:htmx_play_answer")
        items = list(self.quiz_set.items.order_by("order_no"))
        for item in items:
            resp = self.client.post(
                answer_url,
                {"item_id": str(item.id), "selected_index": "0"},
            )
        # 마지막 응답은 결과 화면
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "문제")

        # attempt 상태 확인 (submitted 또는 rewarded)
        attempt = SQAttempt.objects.get(student=self.student, quiz_set=self.quiz_set)
        self.assertIn(attempt.status, ["submitted", "rewarded"])

    def test_already_submitted_redirects_to_result(self):
        # attempt 미리 submitted 상태로 생성
        attempt = SQAttempt.objects.create(
            quiz_set=self.quiz_set,
            student=self.student,
            status="submitted",
            score=2,
            max_score=3,
        )
        # 세션 수동 설정
        session = self.client.session
        session["sq_attempt_id"] = str(attempt.id)
        session.save()

        start_url = reverse("seed_quiz:student_start", kwargs={"class_slug": self.slug})
        resp = self.client.post(start_url, {"number": "7", "name": "홍길동"})
        # 이미 제출된 경우 결과 화면으로 리다이렉트
        self.assertEqual(resp.status_code, 302)
        self.assertIn("result", resp["Location"])
