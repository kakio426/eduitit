import uuid
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from core.models import UserProfile
from happy_seed.models import HSClassroom, HSGuardianConsent, HSStudent
from seed_quiz.models import SQAttempt, SQQuizItem, SQQuizSet
from seed_quiz.services.grading import submit_and_reward

User = get_user_model()


class RetroRewardCommandTest(TestCase):
    def setUp(self):
        username = f"retro_t_{uuid.uuid4().hex[:4]}"
        teacher = User.objects.create_user(
            username=username, password="pw", email=f"{username}@test.com"
        )
        UserProfile.objects.update_or_create(
            user=teacher, defaults={"nickname": username, "role": "school"}
        )
        self.classroom = HSClassroom.objects.create(
            name="소급보상반",
            teacher=teacher,
            slug=f"retro-{uuid.uuid4().hex[:6]}",
        )
        self.quiz_set = SQQuizSet.objects.create(
            classroom=self.classroom,
            target_date=timezone.localdate(),
            preset_type="orthography",
            grade=3,
            title="소급 보상 테스트",
            status="published",
            created_by=teacher,
        )
        for idx in range(1, 4):
            SQQuizItem.objects.create(
                quiz_set=self.quiz_set,
                order_no=idx,
                question_text=f"문제 {idx}",
                choices=["A", "B", "C", "D"],
                correct_index=0,
            )
        self.student = HSStudent.objects.create(
            classroom=self.classroom,
            name="학생1",
            number=1,
            is_active=True,
        )
        HSGuardianConsent.objects.create(student=self.student, status="pending")
        self.attempt = SQAttempt.objects.create(quiz_set=self.quiz_set, student=self.student)

    def test_command_rewards_eligible_attempt(self):
        submit_and_reward(
            attempt_id=self.attempt.id,
            answers={1: 0, 2: 0, 3: 0},
        )
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, "submitted")

        consent = self.student.consent
        consent.status = "approved"
        consent.save(update_fields=["status"])

        out = StringIO()
        call_command(
            "seed_quiz_retro_reward",
            "--classroom-id",
            str(self.classroom.id),
            stdout=out,
        )
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, "rewarded")
        self.assertIn("rewarded=1", out.getvalue())

    def test_command_dry_run_does_not_change_attempt(self):
        submit_and_reward(
            attempt_id=self.attempt.id,
            answers={1: 0, 2: 0, 3: 0},
        )
        consent = self.student.consent
        consent.status = "approved"
        consent.save(update_fields=["status"])

        out = StringIO()
        call_command(
            "seed_quiz_retro_reward",
            "--classroom-id",
            str(self.classroom.id),
            "--dry-run",
            stdout=out,
        )
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, "submitted")
        self.assertIn("[dry-run] candidate=1", out.getvalue())
