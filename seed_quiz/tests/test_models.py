import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import UserProfile
from happy_seed.models import HSClassroom, HSStudent
from seed_quiz.models import SQAttempt, SQGenerationLog, SQQuizItem, SQQuizSet

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
        name="3학년 1반",
        school_name="테스트초등학교",
        teacher=teacher,
        slug=f"test-{uuid.uuid4().hex[:6]}",
    )


def make_quiz_set(classroom, teacher, status="draft"):
    from django.utils import timezone
    return SQQuizSet.objects.create(
        classroom=classroom,
        target_date=timezone.localdate(),
        preset_type="general",
        grade=3,
        title="테스트 퀴즈",
        status=status,
        created_by=teacher,
    )


def make_item(quiz_set, order_no=1):
    return SQQuizItem.objects.create(
        quiz_set=quiz_set,
        order_no=order_no,
        question_text="우리나라 수도는?",
        choices=["부산", "인천", "서울", "대구"],
        correct_index=2,
        explanation="서울입니다.",
    )


class SQQuizSetModelTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher("teacher1")
        self.classroom = make_classroom(self.teacher)

    def test_create_draft(self):
        qs = make_quiz_set(self.classroom, self.teacher)
        self.assertEqual(qs.status, "draft")
        self.assertEqual(str(qs.classroom), str(self.classroom))

    def test_unique_published_constraint(self):
        from django.db import IntegrityError
        from django.utils import timezone

        qs1 = make_quiz_set(self.classroom, self.teacher, status="published")
        # 같은 날짜/프리셋에 두 번째 published는 DB 제약 위반
        with self.assertRaises(Exception):
            SQQuizSet.objects.create(
                classroom=self.classroom,
                target_date=timezone.localdate(),
                preset_type="general",
                grade=3,
                title="두 번째 퀴즈",
                status="published",
                created_by=self.teacher,
            )


class SQQuizItemModelTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher("teacher2")
        self.classroom = make_classroom(self.teacher)
        self.quiz_set = make_quiz_set(self.classroom, self.teacher)

    def test_create_item(self):
        item = make_item(self.quiz_set)
        self.assertEqual(item.order_no, 1)
        self.assertEqual(item.correct_index, 2)
        self.assertEqual(len(item.choices), 4)

    def test_unique_order_no(self):
        make_item(self.quiz_set, order_no=1)
        from django.db import IntegrityError
        with self.assertRaises(Exception):
            make_item(self.quiz_set, order_no=1)


class SQAttemptModelTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher("teacher3")
        self.classroom = make_classroom(self.teacher)
        self.quiz_set = make_quiz_set(self.classroom, self.teacher, status="published")
        self.student = HSStudent.objects.create(
            classroom=self.classroom, name="김학생", number=1
        )

    def test_create_attempt(self):
        attempt = SQAttempt.objects.create(
            quiz_set=self.quiz_set, student=self.student
        )
        self.assertEqual(attempt.status, "in_progress")
        self.assertEqual(attempt.score, 0)

    def test_unique_student_quiz_set(self):
        SQAttempt.objects.create(quiz_set=self.quiz_set, student=self.student)
        with self.assertRaises(Exception):
            SQAttempt.objects.create(quiz_set=self.quiz_set, student=self.student)
