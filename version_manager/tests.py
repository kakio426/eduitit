from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from version_manager.models import Document, DocumentGroup, DocumentVersion


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
