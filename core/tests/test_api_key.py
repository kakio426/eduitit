from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile
from autoarticle.views import ArticleCreateView
from unittest.mock import patch

class APIKeyTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='password',
        )
        self.client.login(username='testuser', password='password')
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = '기존쌤'
        profile.role = 'school'
        profile.save()

    def test_user_profile_creation(self):
        """Test that UserProfile is created automatically"""
        profile = UserProfile.objects.get(user=self.user)
        self.assertIsNotNone(profile)

    def test_settings_view_saves_profile_info(self):
        """Settings saves basic profile info without exposing API key editing."""
        response = self.client.post(
            reverse('settings'),
            {
                'nickname': '테스트쌤',
                'role': 'school',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        self.user.userprofile.refresh_from_db()
        self.assertEqual(self.user.userprofile.nickname, '테스트쌤')
        self.assertEqual(self.user.userprofile.role, 'school')

    def test_settings_view_hides_personal_ai_key_and_shows_roster_hub(self):
        response = self.client.get(reverse('settings'))

        self.assertContains(response, "내 정보와 공용 명부")
        self.assertContains(response, "공용 명부 허브")
        self.assertContains(response, "공용 명부 열기")
        self.assertContains(response, "사인 / 배부 체크")
        self.assertContains(response, "행복씨앗")
        self.assertNotContains(response, "Gemini API Key")
        self.assertNotContains(response, "사주 보관함")

    @patch('core.views.build_teacher_buddy_settings_context')
    def test_settings_view_survives_teacher_buddy_settings_failure(self, mock_build_teacher_buddy_settings_context):
        mock_build_teacher_buddy_settings_context.side_effect = RuntimeError('teacher buddy settings failed')

        response = self.client.get(reverse('settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "내 정보와 공용 명부")
        self.assertIsNone(response.context['teacher_buddy_settings'])
        self.assertEqual(response.context['teacher_buddy_urls'], {})

    @patch('core.views.build_teacher_buddy_avatar_context')
    def test_settings_view_survives_teacher_buddy_avatar_failure(self, mock_build_teacher_buddy_avatar_context):
        mock_build_teacher_buddy_avatar_context.side_effect = RuntimeError('teacher buddy avatar failed')

        response = self.client.get(reverse('settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "내 정보와 공용 명부")
        self.assertIsNone(response.context['teacher_buddy_current_avatar'])

    @patch('os.environ.get')
    def test_article_create_uses_server_key_only(self, mock_env_get):
        """Article creation now uses only the configured server key."""
        mock_env_get.return_value = 'system_key'

        view = ArticleCreateView()
        request = RequestFactory().post('/autoarticle/')
        request.user = self.user

        key, is_master_key = view.get_api_key(request)
        self.assertEqual(key, 'system_key')
        self.assertTrue(is_master_key)
