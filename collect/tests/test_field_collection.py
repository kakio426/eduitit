import csv
import io
import json

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from collect.models import CollectionRequest, Submission


class FieldCollectionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="field_teacher",
            email="field_teacher@example.com",
            password="pw123456",
        )
        self.teacher.userprofile.nickname = "field-teacher"
        self.teacher.userprofile.save(update_fields=["nickname"])

    def _schema(self):
        return [
            {"id": "login_id", "label": "아이디", "kind": "short_text", "required": True, "options": []},
            {"id": "temp_password", "label": "비밀번호", "kind": "secret", "required": True, "options": []},
        ]

    def _request(self, schema=None, **kwargs):
        defaults = {
            "creator": self.teacher,
            "title": "아이디 수합",
            "collection_mode": "fields",
            "field_schema": schema or self._schema(),
            "status": "active",
        }
        defaults.update(kwargs)
        return CollectionRequest.objects.create(**defaults)

    def test_create_fields_request_redirects_and_submit_page_loads(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("collect:request_create"),
            data={
                "collection_mode": "fields",
                "title": "계정 수합",
                "description": "",
                "expected_submitters": "",
                "deadline": "",
                "max_submissions": 20,
                "field_schema_input": json.dumps(self._schema(), ensure_ascii=False),
            },
        )

        self.assertEqual(response.status_code, 302)
        req = CollectionRequest.objects.get(title="계정 수합")
        self.assertEqual(req.collection_mode, "fields")
        self.assertRedirects(
            response,
            f"{reverse('collect:request_detail', args=[req.id])}?entry=created",
            fetch_redirect_response=False,
        )

        submit_response = self.client.get(reverse("collect:submit", args=[req.id]))
        self.assertEqual(submit_response.status_code, 200)
        self.assertContains(submit_response, "아이디")
        self.assertContains(submit_response, "비밀번호")
        self.assertNotContains(submit_response, "임시로 발급한 정보만")
        self.assertNotContains(submit_response, "제출 유형")

    def test_submit_fields_request_success_then_teacher_detail_shows_secret_but_submitter_manage_masks_it(self):
        req = self._request()

        response = self.client.post(
            reverse("collect:submit_process", args=[req.id]),
            data={
                "contributor_name": "김학생",
                "submission_type": "fields",
                "field_login_id": "student01",
                "field_temp_password": "secret123",
            },
        )

        self.assertEqual(response.status_code, 302)
        submission = Submission.objects.get(collection_request=req, contributor_name="김학생")
        self.assertEqual(submission.submission_type, "fields")
        self.assertEqual(submission.field_answers["login_id"], "student01")
        self.assertEqual(submission.field_answers["temp_password"], "secret123")

        manage_response = self.client.get(reverse("collect:submission_manage", args=[submission.management_id]))
        self.assertEqual(manage_response.status_code, 200)
        self.assertContains(manage_response, "student01")
        self.assertContains(manage_response, "••••••")
        self.assertNotContains(manage_response, "secret123")

        self.client.force_login(self.teacher)
        detail_response = self.client.get(reverse("collect:request_detail", args=[req.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "student01")
        self.assertContains(detail_response, "secret123")

    def test_fields_submit_validation_errors_do_not_expose_secret(self):
        req = self._request(
            schema=[
                {"id": "login_id", "label": "아이디", "kind": "short_text", "required": True, "options": []},
                {"id": "temp_password", "label": "비밀번호", "kind": "secret", "required": True, "options": []},
                {"id": "profile", "label": "확인 링크", "kind": "link", "required": True, "options": []},
            ]
        )

        response = self.client.post(
            reverse("collect:submit_process", args=[req.id]),
            data={
                "contributor_name": "김학생",
                "submission_type": "fields",
                "field_login_id": "student01",
                "field_temp_password": "secret123",
                "field_profile": "not-a-url",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "링크 주소를 확인해주세요.")
        self.assertNotContains(response, "secret123")
        self.assertFalse(Submission.objects.filter(collection_request=req).exists())

    def test_fields_file_required_and_size_errors_return_form_page(self):
        req = self._request(
            schema=[
                {"id": "report", "label": "파일", "kind": "file", "required": True, "options": []},
            ],
            max_file_size_mb=1,
        )

        missing_response = self.client.post(
            reverse("collect:submit_process", args=[req.id]),
            data={"contributor_name": "김학생", "submission_type": "fields"},
        )
        self.assertEqual(missing_response.status_code, 200)
        self.assertContains(missing_response, "파일: 파일을 선택해주세요.")

        upload = SimpleUploadedFile(
            "large.txt",
            b"x" * (1024 * 1024 + 1),
            content_type="text/plain",
        )
        large_response = self.client.post(
            reverse("collect:submit_process", args=[req.id]),
            data={
                "contributor_name": "김학생",
                "submission_type": "fields",
                "field_file_report": upload,
            },
        )
        self.assertEqual(large_response.status_code, 200)
        self.assertContains(large_response, "1MB 이하")
        self.assertFalse(Submission.objects.filter(collection_request=req).exists())

    def test_fields_csv_uses_field_labels_as_columns(self):
        req = self._request()
        Submission.objects.create(
            collection_request=req,
            contributor_name="김학생",
            submission_type="fields",
            field_answers={"login_id": "student01", "temp_password": "secret123"},
        )

        self.client.force_login(self.teacher)
        response = self.client.get(reverse("collect:export_csv", args=[req.id]))

        self.assertEqual(response.status_code, 200)
        csv_text = response.content.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(csv_text)))
        rows[0][0] = rows[0][0].lstrip("\ufeff")
        self.assertEqual(rows[0][:5], ["번호", "이름", "소속", "아이디", "비밀번호"])
        self.assertIn("student01", rows[1])
        self.assertIn("secret123", rows[1])

    def test_fields_excel_uses_field_labels_as_columns(self):
        req = self._request()
        Submission.objects.create(
            collection_request=req,
            contributor_name="김학생",
            submission_type="fields",
            field_answers={"login_id": "student01", "temp_password": "secret123"},
        )

        self.client.force_login(self.teacher)
        response = self.client.get(reverse("collect:export_excel", args=[req.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn("attachment;", response["Content-Disposition"])
        workbook = load_workbook(io.BytesIO(response.content))
        sheet = workbook.active
        headers = [cell.value for cell in sheet[1]]
        values = [cell.value for cell in sheet[2]]
        self.assertEqual(headers[:5], ["번호", "이름", "소속", "아이디", "비밀번호"])
        self.assertIn("student01", values)
        self.assertIn("secret123", values)
