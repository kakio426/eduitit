from django.test import TestCase
from fortune.utils.chat_logic import build_system_prompt
from fortune.models import UserSajuProfile
from unittest.mock import MagicMock

class TestChatLogic(TestCase):
    def setUp(self):
        self.mock_profile = MagicMock(spec=UserSajuProfile)
        self.mock_profile.person_name = "TestStudent"  # corrected field
        self.mock_profile.birth_year = 2015  # 11 years old -> use simple vocab
        self.mock_profile.birth_month = 5
        self.mock_profile.birth_day = 5
        self.mock_profile.birth_hour = 12
        self.mock_profile.gender = 'male'

        # Example natal chart (simplified for prompt test)
        self.natal_chart = {
            'year': {'gan': 'gap', 'ji': 'in'},
            'month': {'gan': 'sin', 'ji': 'sa'},
            'day': {'gan': 'gye', 'ji': 'yu'},  # Day Master: Gye (Water)
            'time': {'gan': 'unknown', 'ji': 'unknown'}
        }
    
    def test_build_system_prompt_structure(self):
        """Test the system prompt is generated with correct structure."""
        prompt = build_system_prompt(self.mock_profile, self.natal_chart)

        # Check for persona setup
        self.assertTrue("사주 선생님" in prompt or "Saju Teacher" in prompt)
        # Check for Simple Vocabulary constraint (SIS Rule)
        self.assertTrue("쉬운 어휘" in prompt or "초등학생" in prompt)
        # Check for formatting constraint (Markdown)
        self.assertIn("Markdown", prompt)
        
    def test_build_system_prompt_includes_context(self):
        """Test the prompt includes user context (Day Master)."""
        prompt = build_system_prompt(self.mock_profile, self.natal_chart)
        
        # Should include Day Master identity for the AI (Gye -> Water)
        # Note: Depending on prompt implementation, might check for '계수(癸水)' or 'Water'
        self.assertTrue("계(癸)" in prompt or "Water" in prompt or "계수" in prompt)
        self.assertIn("TestStudent", prompt)  # User name

    def test_build_system_prompt_constraints(self):
        """Test constraints like length and style."""
        prompt = build_system_prompt(self.mock_profile, self.natal_chart)
        
        self.assertTrue("3~4문장" in prompt or "짧게" in prompt)  # Concise response rule
        self.assertTrue("존댓말" in prompt or "친절하게" in prompt)
