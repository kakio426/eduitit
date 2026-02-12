from django.test import TestCase
from collect.models import CollectionRequest, Submission
from django.core.files.storage import default_storage
import uuid

class StorageTest(TestCase):
    def test_get_raw_storage_returns_something(self):
        from collect.models import get_raw_storage
        storage = get_raw_storage()
        self.assertIsNotNone(storage)
        
    def test_model_instantiation_no_cloudinary(self):
        # This tests that importing and creating instances doesn't crash
        # even if Cloudinary is not configured.
        from django.contrib.auth.models import User
        user = User.objects.create_user(username='testuser', password='password')
        req = CollectionRequest.objects.create(
            creator=user,
            title="Test Request",
            access_code="123456"
        )
        self.assertEqual(req.title, "Test Request")
        # Check if storage is indeed default_storage when USE_CLOUDINARY is False
        from django.conf import settings
        if not getattr(settings, 'USE_CLOUDINARY', False):
            self.assertEqual(req.template_file.storage, default_storage)

    def test_signal_cleanup_called(self):
        # This test ensures the signal logic doesn't crash
        from django.contrib.auth.models import User
        user = User.objects.create_user(username='testuser2', password='password')
        req = CollectionRequest.objects.create(
            creator=user,
            title="Cleanup Test",
            access_code="654321"
        )
        req.delete()
        # If it didn't crash, the signal handled the lack of Cloudinary gracefully
