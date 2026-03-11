import importlib
import uuid
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse

from edu_materials.models import EduMaterial


User = get_user_model()


class EduMaterialViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="edu-teacher",
            email="edu-teacher@example.com",
            password="pw123456",
        )
        self.user.userprofile.nickname = "자료선생님"
        self.user.userprofile.save(update_fields=["nickname"])
        self.client = Client()
        self.client.force_login(self.user)

    def test_create_material_from_paste(self):
        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "화산 시뮬레이션",
                "input_mode": "paste",
                "html_content": "<html><body><h1>lesson</h1></body></html>",
            },
        )
        self.assertEqual(response.status_code, 302)
        material = EduMaterial.objects.get(title="화산 시뮬레이션")
        self.assertEqual(material.input_mode, EduMaterial.INPUT_PASTE)
        self.assertIn("lesson", material.html_content)
        self.assertTrue(material.is_published)
        self.assertEqual(material.subject, "OTHER")

    def test_create_material_from_html_file(self):
        upload = SimpleUploadedFile("volcano.html", b"<html><body>volcano</body></html>", content_type="text/html")
        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "파일형 자료",
                "input_mode": "file",
                "html_file": upload,
            },
        )
        self.assertEqual(response.status_code, 302)
        material = EduMaterial.objects.get(title="파일형 자료")
        self.assertEqual(material.input_mode, EduMaterial.INPUT_FILE)
        self.assertEqual(material.original_filename, "volcano.html")
        self.assertIn("volcano", material.html_content)

    def test_non_html_file_is_rejected(self):
        upload = SimpleUploadedFile("volcano.txt", b"plain text", content_type="text/plain")
        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "잘못된 파일",
                "input_mode": "file",
                "html_file": upload,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EduMaterial.objects.filter(title="잘못된 파일").exists())

    def test_create_material_requires_title(self):
        response = self.client.post(
            reverse("edu_materials:create"),
            {
                "title": "",
                "input_mode": "paste",
                "html_content": "<html><body>lesson</body></html>",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(EduMaterial.objects.count(), 0)

    def test_update_material_from_paste(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="이전 제목",
            html_content="<html><body>before</body></html>",
        )

        response = self.client.post(
            reverse("edu_materials:update", args=[material.id]),
            {
                "title": "수정된 제목",
                "html_content": "<html><body>after</body></html>",
            },
        )

        self.assertEqual(response.status_code, 302)
        material.refresh_from_db()
        self.assertEqual(material.title, "수정된 제목")
        self.assertEqual(material.input_mode, EduMaterial.INPUT_PASTE)
        self.assertIn("after", material.html_content)

    def test_delete_material(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="삭제할 자료",
            html_content="<html><body>delete</body></html>",
        )

        response = self.client.post(reverse("edu_materials:delete", args=[material.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(EduMaterial.objects.filter(id=material.id).exists())

    def test_main_view_separates_my_materials_and_shared_materials(self):
        other_user = User.objects.create_user(
            username="another-teacher",
            email="another@example.com",
            password="pw123456",
        )
        other_user.userprofile.nickname = "옆반선생님"
        other_user.userprofile.save(update_fields=["nickname"])

        my_private = EduMaterial.objects.create(
            teacher=self.user,
            title="내 비공개 자료",
            html_content="<html><body>mine</body></html>",
            is_published=False,
        )
        my_public = EduMaterial.objects.create(
            teacher=self.user,
            title="내 공개 자료",
            html_content="<html><body>mine-public</body></html>",
            is_published=True,
        )
        other_public = EduMaterial.objects.create(
            teacher=other_user,
            title="다른 교사 자료",
            html_content="<html><body>other</body></html>",
            is_published=True,
        )

        response = self.client.get(reverse("edu_materials:main"))

        self.assertEqual(response.status_code, 200)
        my_titles = {item.title for item in response.context["my_materials"]}
        shared_titles = {item.title for item in response.context["shared_materials"]}
        self.assertEqual(my_titles, {my_private.title, my_public.title})
        self.assertEqual(shared_titles, {my_public.title, other_public.title})

    def test_run_view_requires_published_material(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="비공개 자료",
            html_content="<html><body>private</body></html>",
            is_published=False,
        )
        response = self.client.get(reverse("edu_materials:run", args=[material.id]))
        self.assertEqual(response.status_code, 404)

    def test_run_view_renders_sandboxed_iframe_and_tracks_views(self):
        material = EduMaterial.objects.create(
            teacher=self.user,
            title="공개 자료",
            html_content="<html><body><script>window.lesson=true;</script></body></html>",
            is_published=True,
        )
        response = self.client.get(reverse("edu_materials:run", args=[material.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sandbox=\"allow-downloads allow-forms allow-modals allow-popups allow-scripts\"")
        material.refresh_from_db()
        self.assertEqual(material.view_count, 1)


class EduMaterialMigrationHelperTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="migration-teacher",
            email="migration-teacher@example.com",
            password="pw123456",
        )
        self.module = importlib.import_module("edu_materials.migrations.0002_import_from_textbooks")
        self.temp_tables = []

    def tearDown(self):
        with connection.cursor() as cursor:
            for table_name in self.temp_tables:
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        super().tearDown()

    def _create_temp_table(self, schema_sql):
        table_name = f"tmp_textbooks_{uuid.uuid4().hex[:8]}"
        self.temp_tables.append(table_name)
        with connection.cursor() as cursor:
            cursor.execute(schema_sql.format(table=table_name))
        return table_name

    def test_legacy_schema_without_source_type_moves_all_rows(self):
        table_name = self._create_temp_table(
            """
            CREATE TABLE "{table}" (
                "id" char(32) NOT NULL PRIMARY KEY,
                "subject" varchar(20) NOT NULL,
                "grade" varchar(50) NULL,
                "unit_title" varchar(200) NOT NULL,
                "title" varchar(200) NOT NULL,
                "content" text NOT NULL,
                "is_published" bool NOT NULL,
                "created_at" datetime NOT NULL,
                "updated_at" datetime NOT NULL,
                "teacher_id" integer NOT NULL,
                "view_count" integer NOT NULL,
                "is_shared" bool NOT NULL
            )
            """
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f'INSERT INTO "{table_name}" (id, subject, grade, unit_title, title, content, is_published, created_at, updated_at, teacher_id, view_count, is_shared) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                [
                    uuid.uuid4().hex,
                    "SCIENCE",
                    "4학년 1학기",
                    "화산과 지진",
                    "레거시 HTML 자료",
                    "<html><body>legacy</body></html>",
                    0,
                    "2026-03-01 09:00:00",
                    "2026-03-01 09:30:00",
                    self.user.id,
                    7,
                    1,
                ],
            )

        schema_editor = SimpleNamespace(connection=connection)
        created = self.module.migrate_legacy_rows(schema_editor, EduMaterial, source_table=table_name)

        self.assertEqual(created, 1)
        material = EduMaterial.objects.get(title="레거시 HTML 자료")
        self.assertEqual(material.teacher_id, self.user.id)
        self.assertEqual(material.input_mode, EduMaterial.INPUT_PASTE)
        self.assertTrue(material.is_published)
        self.assertEqual(material.view_count, 7)

    def test_mixed_schema_skips_pdf_and_moves_html_markdown_rows(self):
        table_name = self._create_temp_table(
            """
            CREATE TABLE "{table}" (
                "id" char(32) NOT NULL PRIMARY KEY,
                "subject" varchar(20) NOT NULL,
                "grade" varchar(50) NULL,
                "unit_title" varchar(200) NOT NULL,
                "title" varchar(200) NOT NULL,
                "content" text NOT NULL,
                "source_type" varchar(20) NOT NULL,
                "pdf_file" varchar(100) NULL,
                "original_filename" varchar(255) NULL,
                "is_published" bool NOT NULL,
                "created_at" datetime NOT NULL,
                "updated_at" datetime NOT NULL,
                "teacher_id" integer NOT NULL,
                "view_count" integer NOT NULL,
                "is_shared" bool NOT NULL
            )
            """
        )
        rows = [
            [uuid.uuid4().hex, "SCIENCE", "4학년 1학기", "화산과 지진", "PDF 자료", "", "pdf", "textbooks/pdf/sample.pdf", "sample.pdf", 1, "2026-03-01 09:00:00", "2026-03-01 09:10:00", self.user.id, 3, 0],
            [uuid.uuid4().hex, "SCIENCE", "4학년 1학기", "화산과 지진", "HTML 자료", "<html><body>html</body></html>", "html", "", "activity.html", 1, "2026-03-01 09:00:00", "2026-03-01 09:10:00", self.user.id, 5, 0],
            [uuid.uuid4().hex, "SCIENCE", "4학년 1학기", "화산과 지진", "Markdown 자료", "# markdown", "markdown", "", "", 0, "2026-03-01 09:00:00", "2026-03-01 09:10:00", self.user.id, 2, 0],
        ]
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    f'INSERT INTO "{table_name}" (id, subject, grade, unit_title, title, content, source_type, pdf_file, original_filename, is_published, created_at, updated_at, teacher_id, view_count, is_shared) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                    row,
                )

        schema_editor = SimpleNamespace(connection=connection)
        created = self.module.migrate_legacy_rows(schema_editor, EduMaterial, source_table=table_name)

        self.assertEqual(created, 2)
        titles = set(EduMaterial.objects.values_list("title", flat=True))
        self.assertIn("HTML 자료", titles)
        self.assertIn("Markdown 자료", titles)
        self.assertNotIn("PDF 자료", titles)

