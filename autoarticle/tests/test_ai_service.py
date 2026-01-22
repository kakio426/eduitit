from unittest.mock import patch, MagicMock
from django.test import TestCase
from autoarticle.engines.ai_service import generate_article_gemini, summarize_article_for_ppt

class AIServiceTest(TestCase):
    @patch('google.genai.Client')
    def test_generate_article_gemini_calls_sdk(self, mock_client_class):
        # Setup mock
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "제목: 테스트 제목\n\n본문 내용\n\n#태그1 #태그2"
        mock_client.models.generate_content.return_value = mock_response
        
        topic_data = {
            'school': '테스트 초교',
            'grade': '1학년',
            'event_name': '테스트 행사',
            'location': '장소',
            'date': '2025-01-01',
            'tone': '격조 있는',
            'keywords': '키워드1'
        }
        
        title, content, hashtags = generate_article_gemini("fake_key", topic_data)
        
        # Verify
        mock_client_class.assert_called_with(api_key="fake_key")
        self.assertEqual(title, "테스트 제목")
        self.assertIn("본문 내용", content)
        self.assertEqual(hashtags, ["태그1", "태그2"])

    @patch('google.genai.Client')
    def test_summarize_article_calls_sdk(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "1. 요약 한 줄\n2. 요약 두 줄"
        mock_client.models.generate_content.return_value = mock_response
        
        summary = summarize_article_for_ppt("긴 기사 내용", api_key="fake_key")
        
        self.assertEqual(len(summary), 2)
        self.assertEqual(summary[0], "1. 요약 한 줄")
