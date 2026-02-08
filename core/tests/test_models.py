from django.test import TestCase
from core.models import SiteConfig


class SiteConfigTestCase(TestCase):
    def test_notebook_manual_url_field_exists(self):
        """Test that SiteConfig has notebook_manual_url field"""
        config = SiteConfig.load()
        # This should not raise AttributeError
        url = config.notebook_manual_url
        self.assertIsNotNone(url)  # Field should exist even if empty
    
    def test_notebook_manual_url_can_be_set(self):
        """Test that notebook_manual_url can be updated"""
        config = SiteConfig.load()
        test_url = "https://notebooklm.google.com/test"
        config.notebook_manual_url = test_url
        config.save()
        
        # Reload and verify
        config_reloaded = SiteConfig.load()
        self.assertEqual(config_reloaded.notebook_manual_url, test_url)
