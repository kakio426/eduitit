from django.test import TestCase
from django.template.loader import get_template


class ModalConsistencyTest(TestCase):
    """Test that base.html contains the unified modal structure"""
    
    def test_base_template_has_unified_modal(self):
        """Verify base.html contains #unifiedModal div"""
        template = get_template('base.html')
        rendered = template.render({})
        
        # Check for modal container
        self.assertIn('id="unifiedModal"', rendered, 
                     "base.html should contain unified modal with id='unifiedModal'")
        
        # Check for close button
        self.assertIn('닫기', rendered,
                     "Modal should have a close button with '닫기' text")
        
    def test_modal_has_backdrop(self):
        """Verify modal has backdrop element"""
        template = get_template('base.html')
        rendered = template.render({})
        
        self.assertIn('modalBackdrop', rendered,
                     "Modal should have backdrop element")
        
    def test_modal_has_content_container(self):
        """Verify modal has content injection point"""
        template = get_template('base.html')
        rendered = template.render({})
        
        self.assertIn('modalContent', rendered,
                     "Modal should have content container")
