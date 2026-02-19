from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from collect.models import CollectionRequest, Submission


class CollectFileCleanupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="collect_cleanup", password="pw123456")
        tpl = SimpleUploadedFile("tpl.txt", b"template", content_type="text/plain")
        self.request_obj = CollectionRequest.objects.create(
            creator=self.user,
            title="req",
            template_file=tpl,
            template_file_name="tpl.txt",
        )
        sub_file = SimpleUploadedFile("sub.txt", b"submission", content_type="text/plain")
        self.submission = Submission.objects.create(
            collection_request=self.request_obj,
            contributor_name="n",
            contributor_affiliation="a",
            submission_type="file",
            file=sub_file,
            original_filename="sub.txt",
        )

    def test_delete_submission_cleans_file(self):
        storage = self.submission.file.storage
        old_name = self.submission.file.name
        with patch.object(storage, "delete", wraps=storage.delete) as mocked_delete:
            with self.captureOnCommitCallbacks(execute=True):
                self.submission.delete()
        mocked_delete.assert_called_once_with(old_name)

    def test_replace_submission_file_cleans_old_file(self):
        old_name = self.submission.file.name
        storage = self.submission.file.storage
        new_file = SimpleUploadedFile("sub2.txt", b"submission2", content_type="text/plain")
        with patch.object(storage, "delete", wraps=storage.delete) as mocked_delete:
            with self.captureOnCommitCallbacks(execute=True):
                self.submission.file = new_file
                self.submission.save(update_fields=["file"])
        mocked_delete.assert_called_once_with(old_name)

    def test_delete_request_cleans_template_file(self):
        storage = self.request_obj.template_file.storage
        old_name = self.request_obj.template_file.name
        with patch.object(storage, "delete", wraps=storage.delete) as mocked_delete:
            with self.captureOnCommitCallbacks(execute=True):
                self.request_obj.delete()
        mocked_delete.assert_any_call(old_name)
