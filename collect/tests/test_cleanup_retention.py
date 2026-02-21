from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from collect.models import CollectionRequest, Submission


class CollectCleanupRetentionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="retention_cleanup",
            password="pw123456",
        )

    def test_closed_request_is_not_archived_when_retention_is_future(self):
        req = CollectionRequest.objects.create(
            creator=self.user,
            title="retention-future",
            status="closed",
            closed_at=timezone.now() - timedelta(days=40),
            retention_until=timezone.now() + timedelta(days=5),
        )
        file_obj = SimpleUploadedFile("sub.txt", b"sub", content_type="text/plain")
        sub = Submission.objects.create(
            collection_request=req,
            contributor_name="n",
            contributor_affiliation="a",
            submission_type="file",
            file=file_obj,
            original_filename="sub.txt",
        )

        call_command("cleanup_collect")

        req.refresh_from_db()
        sub.refresh_from_db()
        self.assertEqual(req.status, "closed")
        self.assertTrue(bool(sub.file))

    def test_old_request_is_not_deleted_when_retention_is_future(self):
        req = CollectionRequest.objects.create(
            creator=self.user,
            title="old-with-retention",
            status="active",
            retention_until=timezone.now() + timedelta(days=3),
        )
        CollectionRequest.objects.filter(id=req.id).update(
            created_at=timezone.now() - timedelta(days=120),
            updated_at=timezone.now() - timedelta(days=120),
        )

        call_command("cleanup_collect")

        self.assertTrue(CollectionRequest.objects.filter(id=req.id).exists())
