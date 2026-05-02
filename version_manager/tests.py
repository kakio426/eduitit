from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from version_manager.models import Document, DocumentGroup, DocumentShareLink, DocumentVersion

User = get_user_model()


class DeleteExpiredVersionsCommandTests(TestCase):
    def setUp(self):
        self.group = DocumentGroup.objects.create(name="가정통신문")

    def _create_document(self, base_name):
        return Document.objects.create(base_name=base_name, group=self.group)

    def _create_version(self, document, version, *, created_at_days_ago, filename=None):
        upload_name = filename or f"{document.base_name}-v{version}.pdf"
        item = DocumentVersion.objects.create(
            document=document,
            version=version,
            upload=SimpleUploadedFile(upload_name, b"%PDF-1.4\nversion-data", content_type="application/pdf"),
            original_filename=upload_name,
        )
        created_at = timezone.now() - timedelta(days=created_at_days_ago)
        DocumentVersion.objects.filter(pk=item.pk).update(created_at=created_at)
        item.refresh_from_db()
        return item

    def test_command_keeps_latest_version_even_if_it_is_older_than_cutoff(self):
        document = self._create_document("학급안내")
        old_version = self._create_version(document, 1, created_at_days_ago=90)
        latest_version = self._create_version(document, 2, created_at_days_ago=80)

        call_command("delete_expired_versions", "--days", "60")

        remaining_ids = set(DocumentVersion.objects.filter(document=document).values_list("id", flat=True))
        self.assertNotIn(old_version.id, remaining_ids)
        self.assertIn(latest_version.id, remaining_ids)

    def test_default_retention_is_sixty_days(self):
        document = self._create_document("주간계획")
        old_but_within_sixty_days = self._create_version(document, 1, created_at_days_ago=45)
        latest_version = self._create_version(document, 2, created_at_days_ago=10)

        call_command("delete_expired_versions")

        remaining_ids = set(DocumentVersion.objects.filter(document=document).values_list("id", flat=True))
        self.assertIn(old_but_within_sixty_days.id, remaining_ids)
        self.assertIn(latest_version.id, remaining_ids)

    def test_deleted_published_version_clears_document_pointer(self):
        document = self._create_document("학부모안내")
        published_version = self._create_version(document, 1, created_at_days_ago=90)
        latest_version = self._create_version(document, 2, created_at_days_ago=5)
        document.published_version = published_version
        document.save(update_fields=["published_version"])

        call_command("delete_expired_versions", "--days", "60")

        document.refresh_from_db()
        self.assertIsNone(document.published_version)
        self.assertTrue(DocumentVersion.objects.filter(pk=latest_version.pk).exists())


class VersionManagerUxFailureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="teacher", email="teacher@example.com", password="pw123456")
        profile = self.user.userprofile
        profile.nickname = "담임선생님"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        UserPolicyConsent.objects.create(
            user=self.user,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=self.user.date_joined,
            agreement_source="test",
        )
        self.group = DocumentGroup.objects.create(name="학년자료")
        self.document = Document.objects.create(base_name="가정통신문", group=self.group)
        self.version = DocumentVersion.objects.create(
            document=self.document,
            version=1,
            upload=SimpleUploadedFile("notice.pdf", b"%PDF-1.4\nbody", content_type="application/pdf"),
            original_filename="notice.pdf",
            uploaded_by=self.user,
        )

    def test_non_staff_publish_recovers_with_permission_message(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("version_manager:set_published", args=[self.document.id, self.version.id]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "권한 없음")
        self.document.refresh_from_db()
        self.assertIsNone(self.document.published_version)

    def test_expired_shared_upload_returns_user_safe_message(self):
        share_link = DocumentShareLink.objects.create(document=self.document, created_by=self.user, is_active=False)

        response = self.client.get(reverse("version_manager:shared_upload", args=[share_link.token]))

        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "링크 확인", status_code=410)
        self.assertNotContains(response, "HttpResponseForbidden", status_code=410)

    def test_missing_shared_upload_returns_user_safe_message(self):
        response = self.client.get(reverse("version_manager:shared_upload", args=["missing-token"]))

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "링크 확인", status_code=404)
        self.assertNotContains(response, "Page not found", status_code=404)

    def test_missing_file_download_returns_to_detail_with_file_message(self):
        self.client.force_login(self.user)
        self.version.upload.delete(save=False)

        response = self.client.get(
            reverse("version_manager:download_version", args=[self.document.id, self.version.id]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "파일 확인")
