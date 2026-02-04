from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import UserProfile

class OnboardingTests(TestCase):
    def setUp(self):
        self.client = Client()
        # User with missing email
        self.user_no_email = User.objects.create_user(username='test_no_email', password='password123')
        # User with default nickname
        self.user_default_nickname = User.objects.create_user(username='test_default', email='test@example.com', password='password123')
        self.user_default_nickname.userprofile.nickname = 'user54'
        self.user_default_nickname.userprofile.save()
        
        # Complete user
        self.user_complete = User.objects.create_user(username='test_complete', email='complete@example.com', password='password123')
        self.user_complete.userprofile.nickname = 'CoolTeacher'
        self.user_complete.userprofile.save()

    def test_middleware_redirects_user_without_email(self):
        self.client.login(username='test_no_email', password='password123')
        response = self.client.get(reverse('home'))
        # Should redirect to update_email
        self.assertRedirects(response, reverse('update_email'))

    def test_middleware_redirects_user_with_default_nickname(self):
        self.client.login(username='test_default', password='password123')
        response = self.client.get(reverse('home'))
        # Should redirect to update_email
        self.assertRedirects(response, reverse('update_email'))

    def test_middleware_allows_complete_user(self):
        self.client.login(username='test_complete', password='password123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_update_email_submission(self):
        self.client.login(username='test_no_email', password='password123')
        # Submit new name and email
        response = self.client.post(reverse('update_email'), {
            'nickname': 'BrandNewName',
            'email': 'brandnew@example.com'
        })
        # Should redirect (either to select_role or home)
        self.assertEqual(response.status_code, 302)
        
        # Verify persistence
        self.user_no_email.refresh_from_db()
        self.assertEqual(self.user_no_email.email, 'brandnew@example.com')
        # We also want to check first_name if we decide to sync it
        self.assertEqual(self.user_no_email.userprofile.nickname, 'BrandNewName')

class AccountDeletionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='delete_me', password='password123')

    def test_delete_account_view_requires_login(self):
        # Using reverse('delete_account') - this should fail initially since the URL doesn't exist
        try:
            url = reverse('delete_account')
        except:
            url = '/delete-account/' # fallback to check if it's there
            
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302) # Redirect to login

    def test_delete_account_execution(self):
        self.client.login(username='delete_me', password='password123')
        # This will fail because the view/URL doesn't exist yet
        try:
            url = reverse('delete_account')
        except:
            self.fail("delete_account URL not defined")
            
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302) # Should redirect to home/login after deletion
        self.assertFalse(User.objects.filter(username='delete_me').exists())
