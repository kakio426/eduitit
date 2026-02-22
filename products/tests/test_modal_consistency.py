from django.test import TestCase
from django.urls import reverse


class ModalConsistencyTest(TestCase):
    """Test that base.html contains the unified modal structure"""
    
    def test_base_template_has_unified_modal(self):
        """Verify rendered page contains #unifiedModal"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        rendered = response.content.decode('utf-8')
        
        # Check for modal container
        self.assertIn('id="unifiedModal"', rendered, 
                     "base.html should contain unified modal with id='unifiedModal'")
        
        # Check for close button
        self.assertIn('aria-label="Close modal"', rendered,
                     "Modal should have an accessible close label")
        
    def test_modal_has_backdrop(self):
        """Verify modal has backdrop element"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        rendered = response.content.decode('utf-8')
        
        self.assertIn('modalBackdrop', rendered,
                     "Modal should have backdrop element")
        
    def test_modal_has_content_container(self):
        """Verify modal has content injection point"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        rendered = response.content.decode('utf-8')
        
        self.assertIn('modalContent', rendered,
                     "Modal should have content container")

    def test_modal_has_mobile_scroll_safe_layout(self):
        """Verify modal panel/layout supports mobile internal scrolling."""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        rendered = response.content.decode('utf-8')

        self.assertIn('items-end md:items-center', rendered)
        self.assertIn('overflow-y-auto overscroll-y-contain', rendered)
        self.assertIn('h-[calc(100dvh-1rem)]', rendered)
