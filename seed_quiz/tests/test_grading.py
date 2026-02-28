import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import UserProfile
from happy_seed.models import HSClassroom, HSGuardianConsent, HSStudent
from seed_quiz.models import SQAttempt, SQAttemptAnswer, SQQuizItem, SQQuizSet
from seed_quiz.services.grading import (
    QUIZ_REWARD_SEEDS,
    apply_retroactive_reward_for_attempt,
    apply_retroactive_rewards_for_student,
    submit_and_reward,
)

User = get_user_model()


def _setup_data():
    username = f"grading_t_{uuid.uuid4().hex[:4]}"
    teacher = User.objects.create_user(
        username=username, password="pw", email=f"{username}@test.com"
    )
    UserProfile.objects.update_or_create(
        user=teacher, defaults={"nickname": username, "role": "school"}
    )
    classroom = HSClassroom.objects.create(
        name="채점반",
        teacher=teacher,
        slug=f"grade-{uuid.uuid4().hex[:6]}",
    )
    quiz_set = SQQuizSet.objects.create(
        classroom=classroom,
        target_date=timezone.localdate(),
        preset_type="orthography",
        grade=3,
        title="채점 테스트",
        status="published",
        created_by=teacher,
    )
    # 3문항 생성
    items = []
    for i in range(1, 4):
        item = SQQuizItem.objects.create(
            quiz_set=quiz_set,
            order_no=i,
            question_text=f"문제 {i}",
            choices=["A", "B", "C", "D"],
            correct_index=0,  # 정답은 항상 인덱스 0
        )
        items.append(item)

    student = HSStudent.objects.create(
        classroom=classroom, name="채점학생", number=1
    )
    attempt = SQAttempt.objects.create(quiz_set=quiz_set, student=student)
    return attempt, items, student


class GradingPerfectScoreApprovedTest(TestCase):
    def setUp(self):
        self.attempt, self.items, self.student = _setup_data()
        # 동의 승인 상태
        HSGuardianConsent.objects.create(student=self.student, status="approved")

    def test_perfect_score_with_consent_rewards_seeds(self):
        answers = {item.order_no: 0 for item in self.items}  # 모두 정답(인덱스0)
        result = submit_and_reward(attempt_id=self.attempt.id, answers=answers)

        self.assertEqual(result.status, "rewarded")
        self.assertEqual(result.score, 3)
        self.assertEqual(result.reward_seed_amount, QUIZ_REWARD_SEEDS)
        self.assertIsNotNone(result.reward_applied_at)
        self.assertEqual(result.consent_snapshot, "approved")

    def test_idempotent_double_call(self):
        answers = {item.order_no: 0 for item in self.items}
        r1 = submit_and_reward(attempt_id=self.attempt.id, answers=answers)
        r2 = submit_and_reward(attempt_id=self.attempt.id, answers=answers)
        self.assertEqual(r1.id, r2.id)
        self.assertEqual(r2.status, "rewarded")
        # HSSeedLedger에 중복 보상 없음 (uuid5 request_id 덕분)
        from happy_seed.models import HSSeedLedger
        reward_request_id = uuid.uuid5(
            uuid.NAMESPACE_URL, f"sq_reward:{self.attempt.id}"
        )
        ledger_count = HSSeedLedger.objects.filter(
            student=self.student, request_id=reward_request_id
        ).count()
        self.assertEqual(ledger_count, 1)


class GradingPerfectScoreNotApprovedTest(TestCase):
    def setUp(self):
        self.attempt, self.items, self.student = _setup_data()
        # 동의 미완료 (consent 없음)

    def test_perfect_score_without_consent_no_reward(self):
        answers = {item.order_no: 0 for item in self.items}
        result = submit_and_reward(attempt_id=self.attempt.id, answers=answers)

        self.assertEqual(result.status, "submitted")
        self.assertEqual(result.score, 3)
        self.assertEqual(result.reward_seed_amount, 0)
        self.assertIsNone(result.reward_applied_at)
        self.assertEqual(result.consent_snapshot, "none")


class GradingPartialScoreTest(TestCase):
    def setUp(self):
        self.attempt, self.items, self.student = _setup_data()
        HSGuardianConsent.objects.create(student=self.student, status="approved")

    def test_partial_score_no_reward(self):
        # 1번만 정답, 2,3번 오답
        answers = {
            self.items[0].order_no: 0,  # 정답
            self.items[1].order_no: 1,  # 오답
            self.items[2].order_no: 2,  # 오답
        }
        result = submit_and_reward(attempt_id=self.attempt.id, answers=answers)

        self.assertEqual(result.status, "submitted")
        self.assertEqual(result.score, 1)
        self.assertEqual(result.reward_seed_amount, 0)


class GradingRetroactiveRewardTest(TestCase):
    def setUp(self):
        self.attempt, self.items, self.student = _setup_data()
        HSGuardianConsent.objects.create(student=self.student, status="pending")

    def test_retroactive_reward_applies_after_consent_approved(self):
        answers = {item.order_no: 0 for item in self.items}
        initial = submit_and_reward(attempt_id=self.attempt.id, answers=answers)
        self.assertEqual(initial.status, "submitted")
        self.assertEqual(initial.reward_seed_amount, 0)
        self.assertEqual(initial.consent_snapshot, "pending")

        consent = self.student.consent
        consent.status = "approved"
        consent.save(update_fields=["status"])

        updated, rewarded_now = apply_retroactive_reward_for_attempt(
            attempt_id=self.attempt.id,
            trigger="test",
        )
        self.assertTrue(rewarded_now)
        self.assertEqual(updated.status, "rewarded")
        self.assertEqual(updated.reward_seed_amount, QUIZ_REWARD_SEEDS)
        self.assertIsNotNone(updated.reward_applied_at)

    def test_retroactive_reward_is_idempotent(self):
        answers = {item.order_no: 0 for item in self.items}
        submit_and_reward(attempt_id=self.attempt.id, answers=answers)
        consent = self.student.consent
        consent.status = "approved"
        consent.save(update_fields=["status"])

        _, first = apply_retroactive_reward_for_attempt(
            attempt_id=self.attempt.id,
            trigger="test_first",
        )
        _, second = apply_retroactive_reward_for_attempt(
            attempt_id=self.attempt.id,
            trigger="test_second",
        )
        self.assertTrue(first)
        self.assertFalse(second)

        from happy_seed.models import HSSeedLedger

        reward_request_id = uuid.uuid5(
            uuid.NAMESPACE_URL, f"sq_reward:{self.attempt.id}"
        )
        ledger_count = HSSeedLedger.objects.filter(
            student=self.student,
            request_id=reward_request_id,
        ).count()
        self.assertEqual(ledger_count, 1)

    def test_retroactive_reward_for_student_rewards_only_eligible_attempts(self):
        answers = {item.order_no: 0 for item in self.items}
        submit_and_reward(attempt_id=self.attempt.id, answers=answers)

        quiz_set_2 = SQQuizSet.objects.create(
            classroom=self.attempt.quiz_set.classroom,
            target_date=timezone.localdate(),
            preset_type="orthography",
            grade=3,
            title="부분정답 세트",
            status="closed",
            created_by=self.attempt.quiz_set.created_by,
        )
        for idx in range(1, 4):
            SQQuizItem.objects.create(
                quiz_set=quiz_set_2,
                order_no=idx,
                question_text=f"추가 문제 {idx}",
                choices=["A", "B", "C", "D"],
                correct_index=0,
            )
        attempt_2 = SQAttempt.objects.create(quiz_set=quiz_set_2, student=self.student)
        SQAttemptAnswer.objects.create(
            attempt=attempt_2,
            item=quiz_set_2.items.get(order_no=1),
            selected_index=1,
            is_correct=False,
        )
        SQAttemptAnswer.objects.create(
            attempt=attempt_2,
            item=quiz_set_2.items.get(order_no=2),
            selected_index=0,
            is_correct=True,
        )
        SQAttemptAnswer.objects.create(
            attempt=attempt_2,
            item=quiz_set_2.items.get(order_no=3),
            selected_index=0,
            is_correct=True,
        )
        attempt_2.score = 2
        attempt_2.max_score = 3
        attempt_2.status = "submitted"
        attempt_2.submitted_at = timezone.now()
        attempt_2.consent_snapshot = "pending"
        attempt_2.save(
            update_fields=[
                "score",
                "max_score",
                "status",
                "submitted_at",
                "consent_snapshot",
            ]
        )

        consent = self.student.consent
        consent.status = "approved"
        consent.save(update_fields=["status"])

        rewarded_count = apply_retroactive_rewards_for_student(student_id=self.student.id, trigger="test_bulk")
        self.assertEqual(rewarded_count, 1)
        self.attempt.refresh_from_db()
        attempt_2.refresh_from_db()
        self.assertEqual(self.attempt.status, "rewarded")
        self.assertEqual(attempt_2.status, "submitted")
