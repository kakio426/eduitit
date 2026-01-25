from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from fortune.views import saju_view
from fortune.models import SajuProfile, Stem, Branch
from fortune.libs import calculator
from unittest.mock import patch, MagicMock
from django.utils import timezone

class IntegrationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        # Ensure profile created
        if not hasattr(self.user, 'saju_profile'):
            SajuProfile.objects.create(user=self.user, gender='M', birth_date_gregorian=timezone.now(), birth_city='Seoul', longitude=127.0)
            
        # Seed basic stems/branches for testing
        stems_data = [
            ('Gap', '甲', 'yang', 'wood'), ('Eul', '乙', 'yin', 'wood'),
            ('Byung', '丙', 'yang', 'fire'), ('Jung', '丁', 'yin', 'fire'),
            ('Moo', '戊', 'yang', 'earth'), ('Gi', '己', 'yin', 'earth'),
            ('Gyung', '庚', 'yang', 'metal'), ('Shin', '辛', 'yin', 'metal'),
            ('Im', '壬', 'yang', 'water'), ('Gye', '癸', 'yin', 'water')
        ]
        branches_data = [
            ('Ja', '子', 'yang', 'water'), ('Chuk', '丑', 'yin', 'earth'),
            ('In', '寅', 'yang', 'wood'), ('Myo', '卯', 'yin', 'wood'),
            ('Jin', '辰', 'yang', 'earth'), ('Sa', '巳', 'yin', 'fire'),
            ('O', '午', 'yang', 'fire'), ('Mi', '未', 'yin', 'earth'),
            ('Shin', '申', 'yang', 'metal'), ('Yoo', '酉', 'yin', 'metal'),
            ('Sool', '戌', 'yang', 'earth'), ('Hae', '亥', 'yin', 'water')
        ]
        
        for n, c, p, e in stems_data: Stem.objects.create(name=n, character=c, polarity=p, element=e)
        for n, c, p, e in branches_data: Branch.objects.create(name=n, character=c, polarity=p, element=e)

    @patch('fortune.views.get_gemini_client')
    def test_view_calls_logic_and_llm(self, mock_get_client):
        """Test that the view calls logic engine first, constructs prompt, then calls LLM"""
        
        # Mock LLM response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Saju Analysis Result"
        mock_client.models.generate_content.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        # Input data
        data = {
            'mode': 'teacher',
            'name': 'TestUser',
            'gender': 'male',
            'birth_year': '1990',
            'birth_month': '5',
            'birth_day': '5',
            'birth_hour': '14',
            'birth_minute': '30',
            'calendar_type': 'solar'
        }
        
        request = self.factory.post('/fortune/saju/', data)
        request.user = self.user
        
        # We need to verify that Logic Engine was actually used.
        # Ideally, we'd patch calculator.get_pillars too to verify call.
        
        with patch('fortune.libs.calculator.get_pillars') as mock_get_pillars:
            mock_get_pillars.return_value = {
                'year': {'stem': Stem.objects.get(name='Gyung'), 'branch': Branch.objects.get(name='O')},
                'month': {'stem': Stem.objects.get(name='Shin'), 'branch': Branch.objects.get(name='Sa')},
                'day': {'stem': Stem.objects.get(name='Byung'), 'branch': Branch.objects.get(name='In')},
                'hour': {'stem': Stem.objects.get(name='Eul'), 'branch': Branch.objects.get(name='Mi')}
            }
            
            # Since view logic changes aren't implemented yet, this test EXPECTS failure or old behavior 
            # if we run it now against OLD view.
            # But the plan says "RED: Write failing tests first".
            # So this test should fail if the view doesn't use calculator yet.
            
            # However, I can't easily mock imports inside the view function unless I patch at top level.
            # `fortune.views` imports `get_prompt` currently. I want it to use logic engine.
            
            response = saju_view(request)
            
            # Assertions
            self.assertEqual(response.status_code, 200)
            mock_get_pillars.assert_called() # Should fail currently
