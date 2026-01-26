from django.test import TestCase
from django.contrib.auth.models import User
from .models import SavedSignature

class SavedSignatureModelTest(TestCase):
    def test_create_saved_signature(self):
        user = User.objects.create_user(username='testuser', password='password')
        signature = SavedSignature.objects.create(
            user=user,
            image_data='data:image/png;base64,TESTDATA'
        )
        self.assertEqual(SavedSignature.objects.count(), 1)
        self.assertEqual(signature.image_data, 'data:image/png;base64,TESTDATA')
