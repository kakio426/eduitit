from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from reservations.models import RecurringSchedule, School, SpecialRoom
from timetable.models import (
    TimetableClassroom,
    TimetableClassInputStatus,
    TimetableDateOverride,
    TimetableRoomPolicy,
    TimetableSharedEvent,
    TimetableSlotAssignment,
    TimetableSnapshot,
    TimetableTeacher,
    TimetableWorkspace,
)
from timetable.services import (
    build_classroom_date_rows,
    build_effective_date_assignments,
    build_effective_event_payloads,
    build_meeting_matrix,
    build_progress_summary,
    build_publish_readiness,
    parse_display_text,
    publish_to_reservations,
    validate_workspace_assignments,
)


User = get_user_model()


class TimetableServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", password="pw12345")
        self.school = School.objects.create(name="테스트학교", slug="test-school", owner=self.user)
        self.room = SpecialRoom.objects.create(school=self.school, name="과학실", icon="🔬")
        self.workspace = TimetableWorkspace.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            grade=3,
            title="2026 1학기 3학년",
            term_start_date=timezone.datetime(2026, 3, 2).date(),
            term_end_date=timezone.datetime(2026, 7, 17).date(),
            days_json=["월", "화", "수", "목", "금"],
            period_labels_json=["1교시", "2교시", "3교시", "4교시"],
        )
        self.classroom1 = TimetableClassroom.objects.create(
            school=self.school,
            school_year=2026,
            grade=3,
            class_no=1,
        )
        self.classroom2 = TimetableClassroom.objects.create(
            school=self.school,
            school_year=2026,
            grade=3,
            class_no=2,
        )
        self.teacher = TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
            target_weekly_hours=4,
        )
        TimetableRoomPolicy.objects.create(workspace=self.workspace, special_room=self.room, capacity_per_slot=1)

    def test_parse_display_text_supports_teacher_and_room(self):
        parsed = parse_display_text("영어(홍길동) @ 과학실")
        self.assertEqual(parsed["subject_name"], "영어")
        self.assertEqual(parsed["teacher_name"], "홍길동")
        self.assertEqual(parsed["room_name"], "과학실")

    def test_validate_workspace_assignments_detects_teacher_conflict(self):
        assignments = [
            TimetableSlotAssignment(
                workspace=self.workspace,
                classroom=self.classroom1,
                day_key="월",
                period_no=1,
                subject_name="영어",
                teacher=self.teacher,
                display_text="영어(홍길동)",
            ),
            TimetableSlotAssignment(
                workspace=self.workspace,
                classroom=self.classroom2,
                day_key="월",
                period_no=1,
                subject_name="음악",
                teacher=self.teacher,
                display_text="음악(홍길동)",
            ),
        ]
        validation = validate_workspace_assignments(self.workspace, assignments, list(self.workspace.room_policies.all()))
        self.assertEqual(validation["summary"]["conflict_count"], 1)
        self.assertTrue(validation["conflicts"])

    def test_validate_workspace_assignments_detects_shared_event_conflict(self):
        event = TimetableSharedEvent.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            scope_type=TimetableSharedEvent.ScopeType.SCHOOL,
            title="체육대회",
            day_key="월",
            period_start=1,
            period_end=1,
        )
        assignments = [
            TimetableSlotAssignment(
                workspace=self.workspace,
                classroom=self.classroom1,
                day_key="월",
                period_no=1,
                subject_name="영어",
                teacher=self.teacher,
                display_text="영어(홍길동)",
            )
        ]
        validation = validate_workspace_assignments(
            self.workspace,
            assignments,
            list(self.workspace.room_policies.all()),
            effective_events=build_effective_event_payloads(self.workspace, [event]),
        )
        self.assertEqual(validation["summary"]["conflict_count"], 1)
        self.assertIn("체육대회", validation["conflicts"][0])

    def test_build_meeting_matrix_marks_existing_and_blocked_slots(self):
        TimetableSlotAssignment.objects.create(
            workspace=self.workspace,
            classroom=self.classroom1,
            day_key="월",
            period_no=1,
            subject_name="영어",
            teacher=self.teacher,
            display_text="영어(홍길동)",
        )
        TimetableSlotAssignment.objects.create(
            workspace=self.workspace,
            classroom=self.classroom2,
            day_key="월",
            period_no=2,
            subject_name="국어",
            display_text="국어",
        )
        matrix = build_meeting_matrix(
            self.workspace,
            self.teacher,
            [self.classroom1, self.classroom2],
            list(self.workspace.assignments.select_related("teacher", "classroom")),
        )
        row1 = matrix["rows"][0]["cells"][0]
        row2 = matrix["rows"][1]["cells"][1]
        self.assertEqual(row1["state"], "assigned")
        self.assertEqual(row2["state"], "blocked")

    def test_build_meeting_matrix_blocks_shared_event_slots(self):
        event = TimetableSharedEvent.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            scope_type=TimetableSharedEvent.ScopeType.GRADE,
            grade=3,
            title="학년 조회",
            day_key="월",
            period_start=1,
            period_end=1,
        )
        matrix = build_meeting_matrix(
            self.workspace,
            self.teacher,
            [self.classroom1],
            [],
            build_effective_event_payloads(self.workspace, [event]),
        )
        self.assertEqual(matrix["rows"][0]["cells"][0]["state"], "blocked")
        self.assertIn("학년 조회", matrix["rows"][0]["cells"][0]["reason"])

    def test_effective_date_assignments_replace_weekly_slot_with_override(self):
        base_assignment = TimetableSlotAssignment(
            workspace=self.workspace,
            classroom=self.classroom1,
            day_key="월",
            period_no=1,
            subject_name="국어",
            display_text="국어",
        )
        override = TimetableDateOverride(
            workspace=self.workspace,
            classroom=self.classroom1,
            date=timezone.datetime(2026, 3, 2).date(),
            period_no=1,
            subject_name="수채화",
            teacher=self.teacher,
            display_text="수채화(홍길동)",
        )
        effective = build_effective_date_assignments(
            self.workspace,
            timezone.datetime(2026, 3, 2).date(),
            [base_assignment],
            [override],
        )
        self.assertEqual(effective["assignments"][0].display_text, "수채화(홍길동)")

    def test_build_classroom_date_rows_marks_specialist_base_slot_blocked(self):
        specialist = TimetableTeacher.objects.create(
            school=self.school,
            name="전담교사",
            teacher_type=TimetableTeacher.TeacherType.SPECIALIST,
        )
        base_assignment = TimetableSlotAssignment(
            workspace=self.workspace,
            classroom=self.classroom1,
            day_key="월",
            period_no=1,
            subject_name="음악",
            teacher=specialist,
            display_text="음악(전담교사)",
        )
        rows = build_classroom_date_rows(
            self.workspace,
            self.classroom1,
            timezone.datetime(2026, 3, 2).date(),
            [base_assignment],
            [],
            [],
        )
        self.assertTrue(rows[0]["is_blocked"])
        self.assertEqual(rows[0]["status_tone"], "blocked")

    def test_publish_to_reservations_skips_capacity_over_one(self):
        TimetableRoomPolicy.objects.filter(workspace=self.workspace, special_room=self.room).update(capacity_per_slot=2)
        TimetableSlotAssignment.objects.create(
            workspace=self.workspace,
            classroom=self.classroom1,
            day_key="월",
            period_no=1,
            subject_name="과학",
            teacher=self.teacher,
            special_room=self.room,
            display_text="과학(홍길동) @ 과학실",
        )
        snapshot = TimetableSnapshot.objects.create(workspace=self.workspace, name="확정본")
        result = publish_to_reservations(snapshot)
        self.assertEqual(result["applied_count"], 0)
        self.assertEqual(RecurringSchedule.objects.count(), 0)
        self.assertTrue(result["warnings"])

    def test_publish_to_reservations_creates_and_updates_recurring_schedule(self):
        assignment = TimetableSlotAssignment.objects.create(
            workspace=self.workspace,
            classroom=self.classroom1,
            day_key="월",
            period_no=1,
            subject_name="과학",
            teacher=self.teacher,
            special_room=self.room,
            display_text="과학(홍길동) @ 과학실",
        )
        snapshot = TimetableSnapshot.objects.create(workspace=self.workspace, name="확정본")
        result = publish_to_reservations(snapshot)
        self.assertEqual(result["applied_count"], 1)
        recurring = RecurringSchedule.objects.get()
        self.assertIn("3-1반", recurring.name)

        assignment.subject_name = "실험"
        assignment.display_text = "실험(홍길동) @ 과학실"
        assignment.save(update_fields=["subject_name", "display_text"])
        snapshot2 = TimetableSnapshot.objects.create(workspace=self.workspace, name="확정본2")
        result2 = publish_to_reservations(snapshot2)
        self.assertEqual(result2["updated_count"], 1)
        recurring.refresh_from_db()
        self.assertIn("실험", recurring.name)

    def test_progress_summary_counts_review_state(self):
        TimetableClassInputStatus.objects.create(
            workspace=self.workspace,
            classroom=self.classroom1,
            status=TimetableClassInputStatus.Status.SUBMITTED,
            submitted_at=timezone.now(),
        )
        TimetableClassInputStatus.objects.create(
            workspace=self.workspace,
            classroom=self.classroom2,
            status=TimetableClassInputStatus.Status.REVIEWED,
            reviewed_at=timezone.now(),
        )
        summary = build_progress_summary(
            [self.classroom1, self.classroom2],
            {
                item.classroom_id: item
                for item in TimetableClassInputStatus.objects.filter(workspace=self.workspace)
            },
        )
        self.assertEqual(summary["review_required_count"], 1)
        self.assertEqual(summary["review_complete_count"], 1)

    def test_publish_readiness_blocks_when_review_is_not_finished(self):
        summary = {
            "total_classes": 2,
            "review_required_count": 1,
            "review_complete_count": 1,
            "editing_count": 0,
        }
        readiness = build_publish_readiness(self.workspace, {"conflicts": [], "warnings": []}, summary)
        self.assertFalse(readiness["can_publish"])
        self.assertEqual(readiness["workflow_stage"], "review_required")
