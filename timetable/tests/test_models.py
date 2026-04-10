from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from reservations.models import School
from timetable.models import (
    TimetableClassroom,
    TimetableClassEditLink,
    TimetableClassInputStatus,
    TimetableDateOverride,
    TimetableSchoolProfile,
    TimetableShareLink,
    TimetableSharePortal,
    TimetableSharedEvent,
    TimetableSnapshot,
    TimetableTeacher,
    TimetableWorkspace,
)


User = get_user_model()


class TimetableModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", password="pw12345")
        self.school = School.objects.create(name="테스트학교", slug="test-school", owner=self.user)

    def test_workspace_scope_is_unique(self):
        TimetableWorkspace.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            grade=3,
            title="2026 1학기 3학년",
        )
        with self.assertRaises(IntegrityError):
            TimetableWorkspace.objects.create(
                school=self.school,
                school_year=2026,
                term="1학기",
                grade=3,
                title="중복 시간표",
            )

    def test_snapshot_keeps_its_own_sheet_data(self):
        workspace = TimetableWorkspace.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            grade=3,
            title="2026 1학기 3학년",
            sheet_data=[{"name": "3-1반", "data": [[None, {"m": "월"}], [{"m": "1교시"}, {"m": "영어(홍길동)"}]]}],
        )
        snapshot = TimetableSnapshot.objects.create(
            workspace=workspace,
            name="확정본",
            sheet_data=workspace.sheet_data,
        )
        workspace.sheet_data = [{"name": "3-1반", "data": [[None, {"m": "월"}], [{"m": "1교시"}, {"m": "국어(김교사)"}]]}]
        workspace.save(update_fields=["sheet_data"])

        snapshot.refresh_from_db()
        self.assertIn("영어", str(snapshot.sheet_data))
        self.assertNotIn("국어", str(snapshot.sheet_data))

    def test_snapshot_keeps_its_own_event_overlay(self):
        workspace = TimetableWorkspace.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            grade=3,
            title="2026 1학기 3학년",
        )
        snapshot = TimetableSnapshot.objects.create(
            workspace=workspace,
            name="확정본",
            events_json=[{"title": "체육대회", "scope_label": "학교 전체", "slot_keys": ["월:1"]}],
        )
        workspace.sheet_data = [{"name": "3-1반", "data": []}]
        workspace.save(update_fields=["sheet_data"])

        snapshot.refresh_from_db()
        self.assertIn("체육대회", str(snapshot.events_json))

    def test_shared_event_validates_scope_and_grade(self):
        school_event = TimetableSharedEvent(
            school=self.school,
            school_year=2026,
            term="1학기",
            scope_type=TimetableSharedEvent.ScopeType.SCHOOL,
            grade=3,
            title="체육대회",
            day_key="월",
            period_start=1,
            period_end=2,
        )
        with self.assertRaises(ValidationError):
            school_event.full_clean()

        grade_event = TimetableSharedEvent(
            school=self.school,
            school_year=2026,
            term="1학기",
            scope_type=TimetableSharedEvent.ScopeType.GRADE,
            title="학년 조회",
            day_key="화",
            period_start=3,
            period_end=2,
        )
        with self.assertRaises(ValidationError):
            grade_event.full_clean()

    def test_share_link_requires_matching_audience_target(self):
        workspace = TimetableWorkspace.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            grade=3,
            title="2026 1학기 3학년",
        )
        snapshot = TimetableSnapshot.objects.create(workspace=workspace, name="확정본")
        classroom = TimetableClassroom.objects.create(
            school=self.school,
            school_year=2026,
            grade=3,
            class_no=1,
        )
        teacher = TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )

        link = TimetableShareLink(
            snapshot=snapshot,
            audience_type=TimetableShareLink.AudienceType.CLASSROOM,
            teacher=teacher,
        )
        with self.assertRaises(ValidationError):
            link.full_clean()

        valid_link = TimetableShareLink(
            snapshot=snapshot,
            audience_type=TimetableShareLink.AudienceType.CLASSROOM,
            classroom=classroom,
            expires_at=timezone.now() + timedelta(days=1),
        )
        valid_link.full_clean()
        self.assertFalse(valid_link.is_expired)

    def test_share_portal_is_unique_per_snapshot_and_tracks_expiry(self):
        workspace = TimetableWorkspace.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            grade=3,
            title="2026 1학기 3학년",
        )
        snapshot = TimetableSnapshot.objects.create(workspace=workspace, name="확정본")
        portal = TimetableSharePortal.objects.create(
            snapshot=snapshot,
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertFalse(portal.is_expired)

        with self.assertRaises(IntegrityError):
            TimetableSharePortal.objects.create(snapshot=snapshot)

    def test_school_profile_validates_preset_and_custom_ranges(self):
        profile = TimetableSchoolProfile(
            school=self.school,
            school_stage=TimetableSchoolProfile.SchoolStage.MIDDLE,
            grade_start=5,
            grade_end=8,
        )
        profile.full_clean()
        self.assertEqual(profile.grade_start, 1)
        self.assertEqual(profile.grade_end, 3)

        invalid_custom = TimetableSchoolProfile(
            school=self.school,
            school_stage=TimetableSchoolProfile.SchoolStage.CUSTOM,
            grade_start=5,
            grade_end=3,
        )
        with self.assertRaises(ValidationError):
            invalid_custom.full_clean()

    def test_class_input_status_and_edit_link_are_unique_per_classroom(self):
        workspace = TimetableWorkspace.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            grade=3,
            title="2026 1학기 3학년",
        )
        classroom = TimetableClassroom.objects.create(
            school=self.school,
            school_year=2026,
            grade=3,
            class_no=1,
        )
        TimetableClassInputStatus.objects.create(workspace=workspace, classroom=classroom)
        TimetableClassEditLink.objects.create(workspace=workspace, classroom=classroom)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TimetableClassInputStatus.objects.create(workspace=workspace, classroom=classroom)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TimetableClassEditLink.objects.create(workspace=workspace, classroom=classroom)

    def test_date_override_is_unique_per_classroom_date_period(self):
        workspace = TimetableWorkspace.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            grade=3,
            title="2026 1학기 3학년",
        )
        classroom = TimetableClassroom.objects.create(
            school=self.school,
            school_year=2026,
            grade=3,
            class_no=1,
        )
        TimetableDateOverride.objects.create(
            workspace=workspace,
            classroom=classroom,
            date=timezone.localdate(),
            period_no=1,
            display_text="수채화",
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TimetableDateOverride.objects.create(
                    workspace=workspace,
                    classroom=classroom,
                    date=timezone.localdate(),
                    period_no=1,
                    display_text="대체 일정",
                )
