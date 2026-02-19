from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from consent.models import SignatureDocument, SignatureRecipient, SignatureRequest


class ConsentFileCleanupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cleanup_teacher", password="pw123456")
        doc_file = SimpleUploadedFile("doc.pdf", b"%PDF-1.4\nA\n%%EOF", content_type="application/pdf")
        self.document = SignatureDocument.objects.create(
            created_by=self.user,
            title="doc",
            original_file=doc_file,
            file_type=SignatureDocument.FILE_TYPE_PDF,
        )
        self.request_obj = SignatureRequest.objects.create(
            created_by=self.user,
            document=self.document,
            title="req",
        )
        signed_pdf = SimpleUploadedFile("signed.pdf", b"%PDF-1.4\nB\n%%EOF", content_type="application/pdf")
        self.recipient = SignatureRecipient.objects.create(
            request=self.request_obj,
            student_name="A",
            parent_name="B",
            phone_number="",
            signed_pdf=signed_pdf,
        )

    def test_delete_recipient_cleans_signed_pdf(self):
        storage = self.recipient.signed_pdf.storage
        old_name = self.recipient.signed_pdf.name
        with patch.object(storage, "delete", wraps=storage.delete) as mocked_delete:
            with self.captureOnCommitCallbacks(execute=True):
                self.recipient.delete()
        mocked_delete.assert_called_once_with(old_name)

    def test_replace_merged_pdf_cleans_old_file(self):
        first = SimpleUploadedFile("merged1.pdf", b"%PDF-1.4\nM1\n%%EOF", content_type="application/pdf")
        self.request_obj.merged_pdf.save("merged1.pdf", first, save=True)
        old_name = self.request_obj.merged_pdf.name
        storage = self.request_obj.merged_pdf.storage

        second = SimpleUploadedFile("merged2.pdf", b"%PDF-1.4\nM2\n%%EOF", content_type="application/pdf")
        with patch.object(storage, "delete", wraps=storage.delete) as mocked_delete:
            with self.captureOnCommitCallbacks(execute=True):
                self.request_obj.merged_pdf = second
                self.request_obj.save(update_fields=["merged_pdf"])
        mocked_delete.assert_called_once_with(old_name)

    def test_delete_request_without_other_refs_deletes_document_file(self):
        doc_storage = self.document.original_file.storage
        doc_name = self.document.original_file.name
        with patch.object(doc_storage, "delete", wraps=doc_storage.delete) as mocked_delete:
            with self.captureOnCommitCallbacks(execute=True):
                self.request_obj.delete()
        self.assertFalse(SignatureDocument.objects.filter(id=self.document.id).exists())
        mocked_delete.assert_any_call(doc_name)
