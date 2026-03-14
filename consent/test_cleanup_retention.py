from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from consent.models import SignatureDocument, SignatureRequest


User = get_user_model()


class ConsentCleanupRetentionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="consent_retention_user",
            password="pw123456",
        )

    def _create_request_with_merged_pdf(self, *, title, created_days_ago):
        document = SignatureDocument.objects.create(
            created_by=self.user,
            title=f"{title}-document",
            original_file=SimpleUploadedFile("origin.pdf", b"%PDF-1.4\norigin\n%%EOF", content_type="application/pdf"),
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        request_item = SignatureRequest.objects.create(
            created_by=self.user,
            document=document,
            title=title,
            status=SignatureRequest.STATUS_COMPLETED,
            merged_pdf=SimpleUploadedFile("merged.pdf", b"%PDF-1.4\nmerged\n%%EOF", content_type="application/pdf"),
        )
        SignatureRequest.objects.filter(id=request_item.id).update(
            created_at=timezone.now() - timedelta(days=created_days_ago)
        )
        request_item.refresh_from_db()
        return request_item

    def test_merged_pdf_is_kept_within_1year(self):
        request_item = self._create_request_with_merged_pdf(
            title="within-1year",
            created_days_ago=120,
        )

        call_command("cleanup_consent")

        request_item.refresh_from_db()
        self.assertTrue(bool(request_item.merged_pdf))

    def test_merged_pdf_is_deleted_after_1year(self):
        request_item = self._create_request_with_merged_pdf(
            title="after-1year",
            created_days_ago=370,
        )

        call_command("cleanup_consent")

        request_item.refresh_from_db()
        self.assertFalse(bool(request_item.merged_pdf))
