from io import BytesIO

import openpyxl
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from reservations.models import School, SpecialRoom
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
from timetable.services import build_template_workbook


User = get_user_model()


class TimetableViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="teacher", password="pw12345", email="teacher@example.com")
        profile, _created = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "담당교사"
        profile.save(update_fields=["nickname"])
        self.school = School.objects.create(name="테스트학교", slug="test-school", owner=self.user)
        SpecialRoom.objects.create(school=self.school, name="과학실", icon="🔬")
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
        self.classroom = TimetableClassroom.objects.create(
            school=self.school,
            school_year=2026,
            grade=3,
            class_no=1,
        )

    def _build_sheet(self, name, monday_text="", tuesday_text=""):
        def _cell(value):
            return {"m": value} if value else None

        return {
            "name": name,
            "id": f"sheet-{name}",
            "data": [
                [None, {"m": "월"}, {"m": "화"}],
                [{"m": "1교시"}, _cell(monday_text), _cell(tuesday_text)],
                [{"m": "2교시"}, None, None],
                [{"m": "3교시"}, None, None],
                [{"m": "4교시"}, None, None],
            ],
        }

    def test_main_page_shows_workspace_creation_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("timetable:main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학년 일괄 만들기")
        self.assertContains(response, "학년 시간표와 반별 링크 만들기")
        self.assertContains(response, "기존 파일 불러오기")

    def test_batch_create_api_creates_stage_workspaces_and_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("timetable:api_setup_batch_create"),
            data={
                "school_slug": self.school.slug,
                "school_year": 2027,
                "term": "1학기",
                "school_stage": "middle",
                "period_count": 6,
                "days_text": "월,화,수,목,금",
                "term_start_date": "2027-03-02",
                "term_end_date": "2027-07-16",
                "class_count_1": 3,
                "class_count_2": 4,
                "class_count_3": 5,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            TimetableWorkspace.objects.filter(school=self.school, school_year=2027, term="1학기").count(),
            3,
        )
        profile = TimetableSchoolProfile.objects.get(school=self.school)
        self.assertEqual(profile.school_stage, TimetableSchoolProfile.SchoolStage.MIDDLE)
        created_workspace = TimetableWorkspace.objects.get(school=self.school, school_year=2027, term="1학기", grade=1)
        self.assertEqual(created_workspace.class_edit_links.count(), 3)

    def test_workspace_autosave_persists_assignments(self):
        self.client.force_login(self.user)
        sheet_data = [
            {
                "name": "3-1반",
                "id": "classroom-1",
                "data": [
                    [None, {"m": "월"}],
                    [{"m": "1교시"}, {"m": "영어(홍길동)"}],
                    [{"m": "2교시"}, None],
                    [{"m": "3교시"}, None],
                    [{"m": "4교시"}, None],
                ],
            }
        ]
        response = self.client.post(
            reverse("timetable:api_autosave", args=[self.workspace.id]),
            data={"sheet_data": sheet_data},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.workspace.refresh_from_db()
        self.assertIn("영어", str(self.workspace.sheet_data))
        self.assertEqual(self.workspace.assignments.count(), 1)

    def test_share_view_renders_class_snapshot(self):
        TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )
        snapshot = TimetableSnapshot.objects.create(
            workspace=self.workspace,
            name="확정본",
            sheet_data=[self._build_sheet("3-1반", "영어(홍길동)")],
        )
        link = TimetableShareLink.objects.create(
            snapshot=snapshot,
            audience_type=TimetableShareLink.AudienceType.CLASSROOM,
            classroom=self.classroom,
        )
        response = self.client.get(reverse("timetable:share_view", args=[link.token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "3-1반 주간 시간표")
        self.assertContains(response, "영어(홍길동)")
        self.assertContains(response, "강사")
        self.assertNotContains(response, 'id="mainNav"', html=True)
        self.assertNotContains(response, "serviceLauncherModal")

    def test_share_view_uses_snapshot_events_json(self):
        snapshot = TimetableSnapshot.objects.create(
            workspace=self.workspace,
            name="확정본",
            sheet_data=[self._build_sheet("3-1반")],
            events_json=[{"title": "체육대회", "scope_label": "학교 전체", "slot_keys": ["월:1"]}],
        )
        link = TimetableShareLink.objects.create(
            snapshot=snapshot,
            audience_type=TimetableShareLink.AudienceType.CLASSROOM,
            classroom=self.classroom,
        )
        response = self.client.get(reverse("timetable:share_view", args=[link.token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "체육대회")

    def test_share_view_shows_upcoming_date_overrides(self):
        snapshot = TimetableSnapshot.objects.create(
            workspace=self.workspace,
            name="확정본",
            sheet_data=[self._build_sheet("3-1반")],
            date_overrides_json=[
                {
                    "classroom_id": self.classroom.id,
                    "classroom_label": self.classroom.label,
                    "date": "2099-05-18",
                    "date_label": "2099-05-18",
                    "week_label": "12주차",
                    "day_key": "월",
                    "period_no": 2,
                    "subject_name": "수채화",
                    "teacher_name": "홍길동",
                    "room_name": "미술실",
                    "display_text": "수채화(홍길동) @ 미술실",
                    "note": "",
                }
            ],
        )
        link = TimetableShareLink.objects.create(
            snapshot=snapshot,
            audience_type=TimetableShareLink.AudienceType.CLASSROOM,
            classroom=self.classroom,
        )
        response = self.client.get(reverse("timetable:share_view", args=[link.token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "다가오는 예외 일정")
        self.assertContains(response, "수채화(홍길동) @ 미술실")

    def test_legacy_import_can_initialize_workspace_from_template(self):
        self.client.force_login(self.user)
        workbook_bytes = build_template_workbook()

        upload = SimpleUploadedFile(
            "legacy.xlsx",
            workbook_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(
            reverse("timetable:legacy_import"),
            {"workspace_id": str(self.workspace.id), "excel_file": upload},
        )
        self.assertEqual(response.status_code, 302)
        self.workspace.refresh_from_db()
        self.assertTrue(self.workspace.sheet_data)
        self.assertGreaterEqual(self.workspace.assignments.count(), 1)

    def test_publish_conflict_returns_409_and_keeps_draft_state(self):
        self.client.force_login(self.user)
        TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )
        TimetableClassroom.objects.create(
            school=self.school,
            school_year=2026,
            grade=3,
            class_no=2,
        )
        sheet_data = [
            self._build_sheet("3-1반", "영어(홍길동)"),
            self._build_sheet("3-2반", "음악(홍길동)"),
        ]
        response = self.client.post(
            reverse("timetable:api_publish", args=[self.workspace.id]),
            data={"sheet_data": sheet_data, "name": "충돌확정"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.status, TimetableWorkspace.Status.DRAFT)
        self.assertIsNone(self.workspace.published_snapshot)
        self.assertEqual(self.workspace.assignments.count(), 2)

    def test_publish_event_conflict_returns_409(self):
        self.client.force_login(self.user)
        TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )
        TimetableSharedEvent.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            scope_type=TimetableSharedEvent.ScopeType.SCHOOL,
            title="체육대회",
            day_key="월",
            period_start=1,
            period_end=1,
        )
        response = self.client.post(
            reverse("timetable:api_publish", args=[self.workspace.id]),
            data={"sheet_data": [self._build_sheet("3-1반", "영어(홍길동)")], "name": "행사충돌"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("체육대회", response.json()["validation"]["conflicts"][0])

    def test_publish_success_returns_portal_url(self):
        self.client.force_login(self.user)
        TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )
        response = self.client.post(
            reverse("timetable:api_publish", args=[self.workspace.id]),
            data={"sheet_data": [self._build_sheet("3-1반", "영어(홍길동)")], "name": "최종안"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["portal_url"])
        self.workspace.refresh_from_db()
        self.assertIsNotNone(self.workspace.published_snapshot)
        self.assertTrue(TimetableSharePortal.objects.filter(snapshot=self.workspace.published_snapshot).exists())
        self.assertEqual(self.workspace.published_snapshot.events_json, [])

    def test_api_events_create_returns_effective_events(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("timetable:api_events", args=[self.workspace.id]),
            data={
                "scope_type": "school",
                "title": "체육대회",
                "day_key": "월",
                "period_start": 1,
                "period_end": 2,
                "note": "오전 행사",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["effective_events"][0]["title"], "체육대회")
        self.assertEqual(TimetableSharedEvent.objects.count(), 1)

    def test_snapshot_restore_restores_workspace_but_keeps_published_snapshot(self):
        self.client.force_login(self.user)
        TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )
        published_snapshot = TimetableSnapshot.objects.create(
            workspace=self.workspace,
            name="기존확정",
            sheet_data=[self._build_sheet("3-1반", "사회(홍길동)")],
        )
        restore_snapshot = TimetableSnapshot.objects.create(
            workspace=self.workspace,
            name="되돌릴안",
            sheet_data=[self._build_sheet("3-1반", "영어(홍길동)")],
        )
        self.workspace.published_snapshot = published_snapshot
        self.workspace.status = TimetableWorkspace.Status.PUBLISHED
        self.workspace.save(update_fields=["published_snapshot", "status", "updated_at"])

        self.client.post(
            reverse("timetable:api_autosave", args=[self.workspace.id]),
            data={"sheet_data": [self._build_sheet("3-1반", "국어(홍길동)")]},
            content_type="application/json",
        )
        response = self.client.post(
            reverse("timetable:api_snapshot_restore", args=[self.workspace.id, restore_snapshot.id]),
        )
        self.assertEqual(response.status_code, 200)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.published_snapshot_id, published_snapshot.id)
        self.assertEqual(self.workspace.status, TimetableWorkspace.Status.DRAFT)
        self.assertIn("영어", str(self.workspace.sheet_data))
        self.assertNotIn("국어", str(self.workspace.sheet_data))

    def test_snapshot_restore_does_not_modify_shared_event_rows(self):
        self.client.force_login(self.user)
        shared_event = TimetableSharedEvent.objects.create(
            school=self.school,
            school_year=2026,
            term="1학기",
            scope_type=TimetableSharedEvent.ScopeType.SCHOOL,
            title="체육대회",
            day_key="월",
            period_start=1,
            period_end=1,
        )
        restore_snapshot = TimetableSnapshot.objects.create(
            workspace=self.workspace,
            name="되돌릴안",
            sheet_data=[self._build_sheet("3-1반", "영어")],
        )
        response = self.client.post(
            reverse("timetable:api_snapshot_restore", args=[self.workspace.id, restore_snapshot.id]),
        )
        self.assertEqual(response.status_code, 200)
        shared_event.refresh_from_db()
        self.assertEqual(shared_event.title, "체육대회")

    def test_snapshot_restore_restores_date_overrides(self):
        self.client.force_login(self.user)
        snapshot = TimetableSnapshot.objects.create(
            workspace=self.workspace,
            name="되돌릴안",
            sheet_data=[self._build_sheet("3-1반", "영어")],
            date_overrides_json=[
                {
                    "classroom_id": self.classroom.id,
                    "classroom_label": self.classroom.label,
                    "date": "2026-05-18",
                    "date_label": "2026-05-18",
                    "week_label": "12주차",
                    "day_key": "월",
                    "period_no": 2,
                    "subject_name": "수채화",
                    "teacher_name": "",
                    "room_name": "",
                    "display_text": "수채화",
                    "note": "",
                    "source": "teacher_link",
                }
            ],
        )
        response = self.client.post(
            reverse("timetable:api_snapshot_restore", args=[self.workspace.id, snapshot.id]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TimetableDateOverride.objects.filter(workspace=self.workspace, date="2026-05-18").exists())

    def test_class_edit_view_requires_active_token(self):
        link = TimetableClassEditLink.objects.create(
            workspace=self.workspace,
            classroom=self.classroom,
        )
        response = self.client.get(reverse("timetable:class_edit", args=[link.token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "3-1반 시간표 입력")

        link.is_active = False
        link.save(update_fields=["is_active", "updated_at"])
        response = self.client.get(reverse("timetable:class_edit", args=[link.token]))
        self.assertEqual(response.status_code, 404)

    def test_class_edit_weekly_autosave_updates_only_one_classroom_and_status(self):
        teacher = TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )
        other_classroom = TimetableClassroom.objects.create(
            school=self.school,
            school_year=2026,
            grade=3,
            class_no=2,
        )
        TimetableClassEditLink.objects.create(workspace=self.workspace, classroom=self.classroom)
        link2 = TimetableClassEditLink.objects.create(workspace=self.workspace, classroom=other_classroom)
        self.client.post(
            reverse("timetable:api_class_edit_weekly_autosave", args=[link2.token]),
            data={
                "editor_name": "3-2 담임",
                "entries": [{"day_key": "월", "period_no": 1, "text": "사회"}],
            },
            content_type="application/json",
        )
        link = TimetableClassEditLink.objects.get(workspace=self.workspace, classroom=self.classroom)
        response = self.client.post(
            reverse("timetable:api_class_edit_weekly_autosave", args=[link.token]),
            data={
                "editor_name": "3-1 담임",
                "entries": [{"day_key": "월", "period_no": 1, "text": f"영어({teacher.name})"}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.workspace.assignments.filter(classroom=self.classroom).count(), 1)
        self.assertEqual(self.workspace.assignments.filter(classroom=other_classroom).count(), 1)
        status = TimetableClassInputStatus.objects.get(workspace=self.workspace, classroom=self.classroom)
        self.assertEqual(status.status, TimetableClassInputStatus.Status.EDITING)

    def test_class_edit_date_override_autosave_stores_override(self):
        TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )
        link = TimetableClassEditLink.objects.create(workspace=self.workspace, classroom=self.classroom)
        response = self.client.post(
            reverse("timetable:api_class_edit_date_override_autosave", args=[link.token]),
            data={
                "editor_name": "3-1 담임",
                "date": "2026-05-18",
                "entries": [{"period_no": 2, "text": "수채화(홍길동)"}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        override = TimetableDateOverride.objects.get(workspace=self.workspace, classroom=self.classroom, date="2026-05-18", period_no=2)
        self.assertEqual(override.subject_name, "수채화")

    def test_class_edit_submit_marks_status_submitted(self):
        link = TimetableClassEditLink.objects.create(workspace=self.workspace, classroom=self.classroom)
        response = self.client.post(
            reverse("timetable:api_class_edit_submit", args=[link.token]),
            data={
                "editor_name": "3-1 담임",
                "mode": "weekly",
                "entries": [{"day_key": "월", "period_no": 1, "text": "국어"}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        status = TimetableClassInputStatus.objects.get(workspace=self.workspace, classroom=self.classroom)
        self.assertEqual(status.status, TimetableClassInputStatus.Status.SUBMITTED)

    def test_review_endpoint_marks_classroom_reviewed(self):
        self.client.force_login(self.user)
        TimetableClassInputStatus.objects.create(
            workspace=self.workspace,
            classroom=self.classroom,
            status=TimetableClassInputStatus.Status.SUBMITTED,
            editor_name="3-1 담임",
        )
        response = self.client.post(
            reverse("timetable:api_review_class_status", args=[self.workspace.id, self.classroom.id]),
            data={"review_note": "확인 완료"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        status = TimetableClassInputStatus.objects.get(workspace=self.workspace, classroom=self.classroom)
        self.assertEqual(status.status, TimetableClassInputStatus.Status.REVIEWED)
        self.assertEqual(status.review_note, "확인 완료")

    def test_meeting_apply_conflict_returns_409(self):
        self.client.force_login(self.user)
        teacher = TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )
        room = SpecialRoom.objects.get(school=self.school, name="과학실")
        classroom2 = TimetableClassroom.objects.create(
            school=self.school,
            school_year=2026,
            grade=3,
            class_no=2,
        )
        response = self.client.post(
            reverse("timetable:api_meeting_apply", args=[self.workspace.id]),
            data={
                "teacher_id": teacher.id,
                "subject_name": "과학",
                "room_id": room.id,
                "selections": [
                    {"classroom_id": self.classroom.id, "day_key": "월", "period_no": 1},
                    {"classroom_id": classroom2.id, "day_key": "월", "period_no": 1},
                ],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.workspace.assignments.count(), 0)

    def test_meeting_apply_event_conflict_returns_409(self):
        self.client.force_login(self.user)
        teacher = TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )
        room = SpecialRoom.objects.get(school=self.school, name="과학실")
        TimetableSharedEvent.objects.create(
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
        response = self.client.post(
            reverse("timetable:api_meeting_apply", args=[self.workspace.id]),
            data={
                "teacher_id": teacher.id,
                "subject_name": "과학",
                "room_id": room.id,
                "selections": [
                    {"classroom_id": self.classroom.id, "day_key": "월", "period_no": 1},
                ],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("학년 조회", response.json()["validation"]["conflicts"][0])

    def test_share_portal_view_lists_class_and_teacher_links(self):
        teacher = TimetableTeacher.objects.create(
            school=self.school,
            name="홍길동",
            teacher_type=TimetableTeacher.TeacherType.INSTRUCTOR,
        )
        snapshot = TimetableSnapshot.objects.create(
            workspace=self.workspace,
            name="확정본",
            sheet_data=[self._build_sheet("3-1반", "영어(홍길동)")],
        )
        portal = TimetableSharePortal.objects.create(snapshot=snapshot)
        TimetableShareLink.objects.create(
            snapshot=snapshot,
            audience_type=TimetableShareLink.AudienceType.CLASSROOM,
            classroom=self.classroom,
        )
        TimetableShareLink.objects.create(
            snapshot=snapshot,
            audience_type=TimetableShareLink.AudienceType.TEACHER,
            teacher=teacher,
        )
        response = self.client.get(reverse("timetable:share_portal", args=[portal.token]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "우리 반 시간표 보기")
        self.assertContains(response, "내 전담 시간표 보기")
        self.assertContains(response, "3-1반")
        self.assertContains(response, "홍길동")
        self.assertNotContains(response, 'id="mainNav"', html=True)
        self.assertNotContains(response, "serviceLauncherModal")
