import os
import unittest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from django.contrib.auth.models import User
from fortune.views import generate_ai_response

class HybridAPITest(unittest.TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
    
    def tearDown(self):
        self.user.delete()

    @patch('fortune.views.genai.Client')
    def test_user_gemini_key_priority(self, mock_genai_client):
        """Test 1: 사용자가 Gemini Key를 가지고 있다면 Gemini가 호출되어야 함"""
        # 사용자에게 키 설정
        # userprofile 모델이 실제 DB에 있어야 하므로 mock을 사용하거나 실제 생성 필요
        # 여기서는 request.user 객체를 mocking하는 것이 빠름
        request = self.factory.post('/fortune/analyze/')
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.userprofile.gemini_api_key = 'SERVER_GEMINI_KEY'

        # Mock Response
        mock_response = MagicMock()
        mock_response.text = "Gemini Response"
        mock_inst = mock_genai_client.return_value
        mock_inst.models.generate_content.return_value = mock_response

        response_text = generate_ai_response("Test Prompt", request)

        self.assertEqual(response_text, "Gemini Response")
        mock_genai_client.assert_called() # GenAI 호출 확인

    @patch('fortune.views.OpenAI')
    @patch.dict(os.environ, {'MASTER_DEEPSEEK_API_KEY': 'SERVER_DEEPSEEK_KEY'})
    def test_master_deepseek_fallback(self, mock_openai):
        """Test 2: 사용자 키가 없고 마스터 키가 있다면 DeepSeek가 호출되어야 함"""
        request = self.factory.post('/fortune/analyze/')
        request.user = MagicMock()
        request.user.is_authenticated = False # 비로그인 사용자 가정 (또는 키 없음)
        
        # Mock Response
        mock_choice = MagicMock()
        mock_choice.message.content = "DeepSeek Response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        mock_client_inst = mock_openai.return_value
        mock_client_inst.chat.completions.create.return_value = mock_response

        response_text = generate_ai_response("Test Prompt", request)

        self.assertEqual(response_text, "DeepSeek Response")
        mock_openai.assert_called() # OpenAI SDK 호출 확인
        # DeepSeek Base URL 확인
        call_args = mock_openai.call_args
        self.assertEqual(call_args.kwargs['base_url'], "https://api.deepseek.com")

    @patch('fortune.views.OpenAI')
    @patch.dict(os.environ, {}, clear=True) # 환경변수 초기화
    def test_no_keys_error(self, mock_openai):
        """Test 3: 아무 키도 없으면 에러 발생"""
        request = self.factory.post('/fortune/analyze/')
        request.user = MagicMock()
        request.user.is_authenticated = False
        request.user.userprofile.gemini_api_key = None

        with self.assertRaises(Exception) as context:
            generate_ai_response("Test Prompt", request)
        
        self.assertIn("API_KEY_MISSING", str(context.exception))
