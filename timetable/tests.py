from io import BytesIO
from datetime import datetime

import openpyxl
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone

from core.models import UserProfile
from reservations.models import RecurringSchedule, School, SpecialRoom
from timetable.models import TimetableSyncLog
from timetable.services import REQUIRED_SHEETS, build_template_workbook


class TimetablePhaseOneTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_main_page_loads(self):
        response = self.client.get("/timetable/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "전담 시간표·특별실 배치 도우미")

    def test_template_download_has_required_sheets(self):
        response = self.client.get("/timetable/template/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        wb = openpyxl.load_workbook(BytesIO(response.content), data_only=True)
        for sheet_name in REQUIRED_SHEETS:
            self.assertIn(sheet_name, wb.sheetnames)

    def test_upload_valid_template_passes_check(self):
        data = build_template_workbook()
        upload = SimpleUploadedFile(
            "timetable_template.xlsx",
            data,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post("/timetable/", {"excel_file": upload})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["check_result"]["is_valid"])
        self.assertIsNotNone(response.context["generated_result"])
        self.assertTrue(response.context["generated_result"]["is_success"])
        self.assertEqual(response.context["generated_result"]["summary"]["unplaced_count"], 0)

    def test_upload_missing_sheet_fails_check(self):
        wb = openpyxl.load_workbook(BytesIO(build_template_workbook()))
        del wb["배치조건"]
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        upload = SimpleUploadedFile(
            "missing_sheet.xlsx",
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post("/timetable/", {"excel_file": upload})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["check_result"]["is_valid"])
        self.assertIn("배치조건", " ".join(response.context["check_result"]["errors"]))
        self.assertIsNone(response.context["generated_result"])

    def test_apply_to_reservation_when_school_selected(self):
        user = User.objects.create_user(
            username="teacher1",
            password="pw-123456",
            email="teacher1@example.com",
        )
        profile = UserProfile.objects.get(user=user)
        profile.nickname = "담당교사"
        profile.save(update_fields=["nickname"])
        school = School.objects.create(name="테스트학교", slug="test-school", owner=user)

        self.client.login(username="teacher1", password="pw-123456")

        wb = openpyxl.load_workbook(BytesIO(build_template_workbook()))
        ws = wb["특별실설정"]
        ws["D2"] = "바로반영"
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        upload = SimpleUploadedFile(
            "apply_sync.xlsx",
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(
            "/timetable/",
            {"excel_file": upload, "reservation_school_slug": school.slug},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["generated_result"]["is_success"])
        self.assertIsNotNone(response.context["integration_result"])
        self.assertGreaterEqual(len(response.context["recent_sync_logs"]), 1)
        self.assertGreaterEqual(response.context["integration_result"]["applied_count"], 1)
        self.assertGreaterEqual(RecurringSchedule.objects.filter(room__school=school).count(), 1)
        self.assertEqual(TimetableSyncLog.objects.filter(user=user).count(), 1)
        latest = TimetableSyncLog.objects.filter(user=user).first()
        self.assertEqual(latest.sync_mode, "direct")
        self.assertEqual(latest.school_slug, school.slug)

    def test_preview_sync_manual_button_flow(self):
        user = User.objects.create_user(
            username="teacher2",
            password="pw-123456",
            email="teacher2@example.com",
        )
        profile = UserProfile.objects.get(user=user)
        profile.nickname = "담당교사2"
        profile.save(update_fields=["nickname"])
        school = School.objects.create(name="미리보기학교", slug="preview-school", owner=user)
        self.client.login(username="teacher2", password="pw-123456")

        upload = SimpleUploadedFile(
            "preview_sync.xlsx",
            build_template_workbook(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        first = self.client.post(
            "/timetable/",
            {"excel_file": upload, "reservation_school_slug": school.slug, "action": "generate"},
        )
        self.assertEqual(first.status_code, 200)
        preview_info = first.context["preview_apply_info"]
        self.assertIsNotNone(preview_info)
        self.assertGreaterEqual(preview_info["preview_count"], 1)

        second = self.client.post(
            "/timetable/",
            {
                "action": "apply_preview",
                "sync_token": preview_info["token"],
                "school_slug": school.slug,
            },
        )
        self.assertEqual(second.status_code, 200)
        self.assertIsNotNone(second.context["integration_result"])
        self.assertGreaterEqual(second.context["integration_result"]["applied_count"], 1)
        self.assertGreaterEqual(RecurringSchedule.objects.filter(room__school=school).count(), 1)
        self.assertTrue(
            TimetableSyncLog.objects.filter(user=user, sync_mode="preview_manual").exists()
        )

    def test_overwrite_existing_is_applied_when_checked(self):
        user = User.objects.create_user(
            username="teacher3",
            password="pw-123456",
            email="teacher3@example.com",
        )
        profile = UserProfile.objects.get(user=user)
        profile.nickname = "담당교사3"
        profile.save(update_fields=["nickname"])
        school = School.objects.create(name="덮어쓰기학교", slug="overwrite-school", owner=user)
        room = SpecialRoom.objects.create(school=school, name="과학실", icon="🔬")
        existing = RecurringSchedule.objects.create(
            room=room,
            day_of_week=1,  # 화
            period=2,
            name="기존 고정수업",
        )

        self.client.login(username="teacher3", password="pw-123456")

        wb = openpyxl.load_workbook(BytesIO(build_template_workbook()))
        ws_special = wb["특별실설정"]
        ws_special["D2"] = "바로반영"
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        upload_without_overwrite = SimpleUploadedFile(
            "without_overwrite.xlsx",
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        first = self.client.post(
            "/timetable/",
            {
                "excel_file": upload_without_overwrite,
                "reservation_school_slug": school.slug,
                "action": "generate",
            },
        )
        self.assertEqual(first.status_code, 200)
        existing.refresh_from_db()
        self.assertEqual(existing.name, "기존 고정수업")
        self.assertGreaterEqual(first.context["integration_result"]["conflict_count"], 1)

        upload_with_overwrite = SimpleUploadedFile(
            "with_overwrite.xlsx",
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        second = self.client.post(
            "/timetable/",
            {
                "excel_file": upload_with_overwrite,
                "reservation_school_slug": school.slug,
                "overwrite_existing": "on",
                "action": "generate",
            },
        )
        self.assertEqual(second.status_code, 200)
        existing.refresh_from_db()
        self.assertNotEqual(existing.name, "기존 고정수업")
        self.assertGreaterEqual(second.context["integration_result"]["updated_count"], 1)
        self.assertTrue(
            TimetableSyncLog.objects.filter(
                user=user,
                sync_mode="direct",
                overwrite_existing=True,
            ).exists()
        )

    def test_download_sync_logs_csv_requires_login(self):
        response = self.client.get("/timetable/sync-logs.csv")
        self.assertEqual(response.status_code, 302)

    def test_download_sync_logs_csv_contains_user_logs(self):
        user = User.objects.create_user(
            username="teacher4",
            password="pw-123456",
            email="teacher4@example.com",
        )
        profile = UserProfile.objects.get(user=user)
        profile.nickname = "담당교사4"
        profile.save(update_fields=["nickname"])

        TimetableSyncLog.objects.create(
            user=user,
            school_slug="csv-school",
            school_name="CSV학교",
            sync_mode="direct",
            sync_options_text="바로반영",
            overwrite_existing=False,
            status="success",
            applied_count=3,
            updated_count=0,
            skipped_count=1,
            conflict_count=0,
            room_created_count=1,
            summary_text="새로 반영 3건",
            payload={},
        )

        self.client.login(username="teacher4", password="pw-123456")
        response = self.client.get("/timetable/sync-logs.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        content = response.content.decode("utf-8-sig")
        self.assertIn("실행시각", content)
        self.assertIn("CSV학교", content)
        self.assertIn("바로반영", content)

    def test_download_sync_logs_csv_filters_school_and_period(self):
        user = User.objects.create_user(
            username="teacher5",
            password="pw-123456",
            email="teacher5@example.com",
        )
        profile = UserProfile.objects.get(user=user)
        profile.nickname = "담당교사5"
        profile.save(update_fields=["nickname"])

        in_range = TimetableSyncLog.objects.create(
            user=user,
            school_slug="school-a",
            school_name="가람초",
            sync_mode="direct",
            sync_options_text="바로반영",
            overwrite_existing=False,
            status="success",
            applied_count=2,
            updated_count=0,
            skipped_count=0,
            conflict_count=0,
            room_created_count=0,
            summary_text="포함건",
            payload={},
        )
        TimetableSyncLog.objects.filter(pk=in_range.pk).update(
            created_at=timezone.make_aware(datetime(2026, 1, 10, 9, 0, 0))
        )

        out_of_range = TimetableSyncLog.objects.create(
            user=user,
            school_slug="school-a",
            school_name="가람초",
            sync_mode="direct",
            sync_options_text="바로반영",
            overwrite_existing=False,
            status="success",
            applied_count=1,
            updated_count=0,
            skipped_count=0,
            conflict_count=0,
            room_created_count=0,
            summary_text="기간제외건",
            payload={},
        )
        TimetableSyncLog.objects.filter(pk=out_of_range.pk).update(
            created_at=timezone.make_aware(datetime(2026, 2, 10, 9, 0, 0))
        )

        other_school = TimetableSyncLog.objects.create(
            user=user,
            school_slug="school-b",
            school_name="나래초",
            sync_mode="direct",
            sync_options_text="바로반영",
            overwrite_existing=False,
            status="success",
            applied_count=1,
            updated_count=0,
            skipped_count=0,
            conflict_count=0,
            room_created_count=0,
            summary_text="학교제외건",
            payload={},
        )
        TimetableSyncLog.objects.filter(pk=other_school.pk).update(
            created_at=timezone.make_aware(datetime(2026, 1, 12, 9, 0, 0))
        )

        self.client.login(username="teacher5", password="pw-123456")
        response = self.client.get(
            "/timetable/sync-logs.csv",
            {
                "log_school_slug": "school-a",
                "log_date_from": "2026-01-01",
                "log_date_to": "2026-01-31",
            },
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8-sig")
        self.assertIn("포함건", content)
        self.assertNotIn("기간제외건", content)
        self.assertNotIn("학교제외건", content)

    def test_main_recent_sync_logs_filters_and_csv_query(self):
        user = User.objects.create_user(
            username="teacher6",
            password="pw-123456",
            email="teacher6@example.com",
        )
        profile = UserProfile.objects.get(user=user)
        profile.nickname = "담당교사6"
        profile.save(update_fields=["nickname"])

        included = TimetableSyncLog.objects.create(
            user=user,
            school_slug="school-c",
            school_name="다온초",
            sync_mode="direct",
            sync_options_text="바로반영",
            overwrite_existing=False,
            status="success",
            applied_count=1,
            updated_count=0,
            skipped_count=0,
            conflict_count=0,
            room_created_count=0,
            summary_text="목록포함건",
            payload={},
        )
        TimetableSyncLog.objects.filter(pk=included.pk).update(
            created_at=timezone.make_aware(datetime(2026, 1, 5, 10, 0, 0))
        )

        excluded = TimetableSyncLog.objects.create(
            user=user,
            school_slug="school-c",
            school_name="다온초",
            sync_mode="direct",
            sync_options_text="바로반영",
            overwrite_existing=False,
            status="success",
            applied_count=1,
            updated_count=0,
            skipped_count=0,
            conflict_count=0,
            room_created_count=0,
            summary_text="목록제외건",
            payload={},
        )
        TimetableSyncLog.objects.filter(pk=excluded.pk).update(
            created_at=timezone.make_aware(datetime(2026, 2, 5, 10, 0, 0))
        )

        self.client.login(username="teacher6", password="pw-123456")
        response = self.client.get(
            "/timetable/",
            {
                "log_school_slug": "school-c",
                "log_date_from": "2026-01-01",
                "log_date_to": "2026-01-31",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["recent_sync_logs"]), 1)
        self.assertEqual(response.context["recent_sync_logs"][0].summary_text, "목록포함건")
        self.assertIn("log_school_slug=school-c", response.context["csv_download_query"])
