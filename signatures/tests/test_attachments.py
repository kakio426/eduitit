import os
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from signatures.models import TrainingSession, TrainingSessionAttachment


User = get_user_model()


class SignatureAttachmentTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_root = tempfile.mkdtemp(prefix="signatures-tests-")
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(
            username="signature_attachment_owner",
            password="pw12345",
            email="signature_attachment_owner@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "signature_attachment_owner", "role": "school"},
        )
        self.client.force_login(self.user)

    def _session_datetime_value(self, *, days=1):
        session_dt = timezone.localtime(timezone.now() + timedelta(days=days))
        return session_dt.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")

    def _make_file(self, name, size=32, content_type="application/octet-stream"):
        return SimpleUploadedFile(name, b"x" * size, content_type=content_type)

    def _create_session(self, *, is_active=True):
        return TrainingSession.objects.create(
            title="첨부 테스트 연수",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=1),
            location="시청각실",
            created_by=self.user,
            is_active=is_active,
        )

    def test_create_rejects_more_than_ten_attachments(self):
        response = self.client.post(
            reverse("signatures:create"),
            data={
                "title": "첨부 초과 테스트",
                "print_title": "",
                "instructor": "강사",
                "datetime": self._session_datetime_value(days=2),
                "location": "시청각실",
                "description": "",
                "shared_roster_group": "",
                "expected_count": "",
                "is_active": "on",
                "attachments": [
                    self._make_file(f"guide-{index}.pdf", size=64, content_type="application/pdf")
                    for index in range(11)
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "첨부 파일은 최대 10개까지 넣을 수 있습니다.")
        self.assertFalse(TrainingSession.objects.filter(title="첨부 초과 테스트").exists())

    def test_create_rejects_attachment_batch_over_ten_megabytes(self):
        response = self.client.post(
            reverse("signatures:create"),
            data={
                "title": "첨부 용량 초과 테스트",
                "print_title": "",
                "instructor": "강사",
                "datetime": self._session_datetime_value(days=2),
                "location": "시청각실",
                "description": "",
                "shared_roster_group": "",
                "expected_count": "",
                "is_active": "on",
                "attachments": [
                    self._make_file("part-1.pdf", size=6 * 1024 * 1024, content_type="application/pdf"),
                    self._make_file("part-2.hwp", size=5 * 1024 * 1024, content_type="application/x-hwp"),
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "첨부 파일 전체 용량은 10.0MB 이하로 맞춰 주세요.")
        self.assertFalse(TrainingSession.objects.filter(title="첨부 용량 초과 테스트").exists())

    def test_detail_page_shows_share_package_and_attachment_summary(self):
        session = self._create_session()
        TrainingSessionAttachment.objects.create(
            training_session=session,
            file=self._make_file("meeting-guide.pdf", size=512, content_type="application/pdf"),
            original_name="meeting-guide.pdf",
        )
        TrainingSessionAttachment.objects.create(
            training_session=session,
            file=self._make_file("meeting-note.hwpx", size=1024, content_type="application/octet-stream"),
            original_name="meeting-note.hwpx",
        )

        response = self.client.get(reverse("signatures:detail", kwargs={"uuid": session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "공유 패키지 복사")
        self.assertContains(response, "첨부 2개 포함")
        self.assertContains(response, "meeting-guide.pdf")
        self.assertContains(response, "meeting-note.hwpx")
        self.assertContains(response, "첨부 파일 2개 확인 후 서명 부탁드립니다.")
        self.assertContains(response, "아래 링크에서 로그인 없이 바로 서명하실 수 있습니다.")

    def test_edit_can_remove_old_attachment_and_add_new_one(self):
        session = self._create_session()
        old_attachment = TrainingSessionAttachment.objects.create(
            training_session=session,
            file=self._make_file("old-guide.pdf", size=128, content_type="application/pdf"),
            original_name="old-guide.pdf",
        )
        old_path = old_attachment.file.path

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("signatures:edit", kwargs={"uuid": session.uuid}),
                data={
                    "title": session.title,
                    "print_title": "",
                    "instructor": session.instructor,
                    "datetime": self._session_datetime_value(days=3),
                    "location": session.location,
                    "description": "",
                    "shared_roster_group": "",
                    "expected_count": "",
                    "is_active": "on",
                    "remove_attachment_ids": [str(old_attachment.id)],
                    "attachments": [
                        self._make_file("new-guide.hwpx", size=256, content_type="application/octet-stream"),
                    ],
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        attachments = list(session.attachments.order_by("sort_order", "id"))
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].original_name, "new-guide.hwpx")
        self.assertContains(response, "첨부 파일 1개를 추가했습니다.")
        self.assertContains(response, "첨부 파일 1개를 제거했습니다.")
        self.assertFalse(os.path.exists(old_path))

    def test_public_sign_page_lists_attachments_and_public_download_blocks_when_closed(self):
        session = self._create_session(is_active=True)
        attachment = TrainingSessionAttachment.objects.create(
            training_session=session,
            file=self._make_file("meeting-pack.hwpx", size=300, content_type="application/octet-stream"),
            original_name="meeting-pack.hwpx",
        )
        public_download_url = reverse(
            "signatures:sign_attachment_download",
            kwargs={"uuid": session.uuid, "attachment_id": attachment.id},
        )
        teacher_download_url = reverse(
            "signatures:attachment_download",
            kwargs={"uuid": session.uuid, "attachment_id": attachment.id},
        )

        response = self.client.get(reverse("signatures:sign", kwargs={"uuid": session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "첨부된 서류")
        self.assertContains(response, "meeting-pack.hwpx")
        self.assertContains(response, public_download_url)

        public_download_response = self.client.get(public_download_url)
        self.assertEqual(public_download_response.status_code, 200)
        self.assertEqual(public_download_response["Cache-Control"], "no-store, private")
        self.assertIn("attachment;", public_download_response["Content-Disposition"])
        self.assertIn("meeting-pack.hwpx", public_download_response["Content-Disposition"])

        session.is_active = False
        session.save(update_fields=["is_active"])

        closed_public_response = self.client.get(public_download_url)
        self.assertEqual(closed_public_response.status_code, 404)

        teacher_download_response = self.client.get(teacher_download_url)
        self.assertEqual(teacher_download_response.status_code, 200)
        self.assertIn("meeting-pack.hwpx", teacher_download_response["Content-Disposition"])

    def test_deleting_session_removes_attachment_files_from_storage(self):
        session = self._create_session()
        attachment = TrainingSessionAttachment.objects.create(
            training_session=session,
            file=self._make_file("cleanup-target.pdf", size=200, content_type="application/pdf"),
            original_name="cleanup-target.pdf",
        )
        attachment_path = attachment.file.path

        self.assertTrue(os.path.exists(attachment_path))

        with self.captureOnCommitCallbacks(execute=True):
            session.delete()

        self.assertFalse(os.path.exists(attachment_path))
