from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import SiteConfig


class AdminDashboardViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        # UserProfile is auto-created via signal, but ensure it exists
        from core.models import UserProfile
        UserProfile.objects.get_or_create(user=self.superuser)
        
        # Create regular user
        self.regular_user = User.objects.create_user(
            username='user',
            email='user@test.com',
            password='testpass123'
        )
        UserProfile.objects.get_or_create(user=self.regular_user)
    
    def test_admin_can_update_notebook_manual_url(self):
        """Test that superuser can update notebook_manual_url via POST"""
        self.client.login(username='admin', password='testpass123')
        
        test_url = "https://notebooklm.google.com/notebook/test123"
        response = self.client.post(
            reverse('admin_dashboard'),
            {'notebook_manual_url': test_url}
        )
        
        # Should redirect or return 200
        self.assertIn(response.status_code, [200, 302])
        
        # Verify URL was saved
        config = SiteConfig.load()
        self.assertEqual(config.notebook_manual_url, test_url)
    
    def test_non_superuser_cannot_access_admin_dashboard(self):
        """Test that regular users cannot access admin dashboard"""
        self.client.login(username='user', password='testpass123')
        
        response = self.client.get(reverse('admin_dashboard'))
        
        # Should redirect to home
        self.assertEqual(response.status_code, 302)
