from django.test import TestCase
from portfolio.models import Achievement
from django.core.files.uploadedfile import SimpleUploadedFile
from cloudinary_storage.storage import MediaCloudinaryStorage
import os

class StorageIntegrationTest(TestCase):
    def test_achievement_uses_cloudinary_storage(self):
        # Create a dummy achievement
        achievement = Achievement(title="Test", issuer="Test")
        # Check the storage class of the field
        # Achievement.image.field.storage is usually set at class definition time
        storage = achievement.image.field.storage
        print(f"DEBUG: Achievement image field storage: {storage}")
        
        # In a correctly configured Cloudinary setup, this should be MediaCloudinaryStorage
        self.assertIsInstance(storage, MediaCloudinaryStorage, 
                             f"Storage should be MediaCloudinaryStorage, but got {type(storage)}")

    def test_image_url_generation(self):
        # This test might fail if Cloudinary credentials are not valid in the test env,
        # but we can at least check if it attempts to use Cloudinary.
        # Minimal valid PNG
        image_content = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        image_file = SimpleUploadedFile("test_image.png", image_content, content_type="image/png")
        
        achievement = Achievement.objects.create(
            title="URL Test",
            issuer="Test",
            date_awarded="2024-01-01",
            image=image_file
        )
        
        url = achievement.image.url
        print(f"DEBUG: Generated URL: {url}")
        
        # If it's correctly using Cloudinary, the URL should NOT start with /media/
        self.assertIn("cloudinary", url.lower(), f"URL should contain 'cloudinary', but got: {url}")
        self.assertTrue(url.startswith("https://"), f"URL should be https, but got: {url}")
