from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

class AuthTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')

    def test_login_url_exists(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_login_functional(self):
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 302)  # Should redirect after login
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_logout_functional(self):
        self.client.login(username='testuser', password='password123')
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertFalse('_auth_user_id' in self.client.session)
