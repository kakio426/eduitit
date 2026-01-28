
import os
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from fortune.views import generate_ai_response, DEEPSEEK_MODEL_NAME

class TestDeepSeekStreaming(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.post('/fortune/api/streaming/')
        self.request.user = MagicMock()
        self.request.user.is_authenticated = False # Force DeepSeek path (assuming no user key)
        self.prompt = "Test Prompt"

    @patch('fortune.views.get_user_gemini_key', return_value=None)
    @patch.dict(os.environ, {'MASTER_DEEPSEEK_API_KEY': 'test-key'})
    @patch('fortune.views.OpenAI')
    def test_deepseek_streaming_success(self, mock_openai, mock_get_key):
        """DeepSeek 스트리밍이 정상적으로 청크를 반환하는지 테스트"""
        # Mock OpenAI Client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock Stream Response
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"))]
        
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock(delta=MagicMock(content=" World"))]
        
        mock_client.chat.completions.create.return_value = [chunk1, chunk2]

        # Execute
        generator = generate_ai_response(self.prompt, self.request)
        result = list(generator)

        # Verify
        self.assertEqual(result, ["Hello", " World"])
        mock_client.chat.completions.create.assert_called_with(
            model=DEEPSEEK_MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a professional Saju (Four Pillars of Destiny) master."},
                {"role": "user", "content": self.prompt}
            ],
            stream=True
        )

    @patch('fortune.views.get_user_gemini_key', return_value=None)
    @patch.dict(os.environ, {'MASTER_DEEPSEEK_API_KEY': 'test-key'})
    @patch('fortune.views.OpenAI')
    @patch('fortune.views.logger')
    def test_deepseek_streaming_empty(self, mock_logger, mock_openai, mock_get_key):
        """DeepSeek 스트리밍이 비어있을 때 예외를 발생시키는지 테스트"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Empty Stream
        mock_client.chat.completions.create.return_value = []

        # Execute & Verify
        with self.assertRaisesMessage(Exception, "DeepSeek API returned empty response"):
            list(generate_ai_response(self.prompt, self.request))
            
        mock_logger.warning.assert_called_with("DeepSeek stream yielded 0 chunks.")

    @patch('fortune.views.get_user_gemini_key', return_value=None)
    @patch.dict(os.environ, {'MASTER_DEEPSEEK_API_KEY': 'test-key'})
    @patch('fortune.views.OpenAI')
    def test_deepseek_api_error(self, mock_openai, mock_get_key):
        """DeepSeek API 호출 중 에러 발생 시 재시도 로직 및 예외 전파 테스트"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Simulate Exception
        mock_client.chat.completions.create.side_effect = Exception("API Connection Error")

        # Execute & Verify
        with self.assertRaisesMessage(Exception, "API Connection Error"):
            list(generate_ai_response(self.prompt, self.request))
