from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile
from autoarticle.views import ArticleCreateView
from unittest.mock import patch, MagicMock
import os

class APIKeyTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')
        # Ensure profile exists (handled by signal, but good to double check or create if signal failed in test env?)
        # Signals usually run in TestCase.

    def test_user_profile_creation(self):
        """Test that UserProfile is created automatically"""
        profile = UserProfile.objects.get(user=self.user)
        self.assertIsNotNone(profile)

    def test_settings_view_saves_key(self):
        """Test the settings form submission"""
        response = self.client.post(reverse('settings'), {
            'gemini_api_key': 'new_user_key'
        })
        self.assertEqual(response.status_code, 200)
        
        # Refresh from DB
        self.user.userprofile.refresh_from_db()
        self.assertEqual(self.user.userprofile.gemini_api_key, 'new_user_key')

    @patch('os.environ.get')
    def test_api_key_priority(self, mock_env_get):
        """Test that user key takes precedence over environment variable"""
        mock_env_get.return_value = 'system_key'
        
        view = ArticleCreateView()
        request = RequestFactory().post('/autoarticle/')
        request.user = self.user
        
        # Case 1: No user key set (should use system key)
        # Ensure profile exists and key is empty
        profile, created = UserProfile.objects.get_or_create(user=self.user)
        profile.gemini_api_key = ''
        profile.save()
        
        key = view.get_api_key(request)
        self.assertEqual(key, 'system_key')
        
        # Case 2: User key set (should use user key)
        profile.gemini_api_key = 'user_key'
        profile.save()
        
        # Refresh user to pick up profile changes
        self.user.refresh_from_db()
        request.user = self.user
        
        key = view.get_api_key(request)
        self.assertEqual(key, 'user_key')
