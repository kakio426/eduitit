from django.test import TestCase, RequestFactory
from core.context_processors import site_config
from core.models import SiteConfig


class ContextProcessorTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        
    def test_site_config_includes_notebook_manual_url(self):
        """Test that site_config context processor includes notebook_manual_url"""
        # Set up test data
        config = SiteConfig.load()
        test_url = "https://notebooklm.google.com/test"
        config.notebook_manual_url = test_url
        config.save()
        
        # Create fake request
        request = self.factory.get('/')
        
        # Get context
        context = site_config(request)
        
        # Verify notebook_manual_url is in context
        self.assertIn('notebook_manual_url', context)
        self.assertEqual(context['notebook_manual_url'], test_url)
