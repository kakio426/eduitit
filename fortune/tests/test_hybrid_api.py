import os
from unittest.mock import patch, MagicMock

from django.test import RequestFactory, SimpleTestCase

from fortune.views import generate_ai_response


class HybridAPITest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("fortune.views.OpenAI")
    @patch.dict(os.environ, {"MASTER_DEEPSEEK_API_KEY": "SERVER_DEEPSEEK_KEY"})
    def test_authenticated_user_uses_master_deepseek(self, mock_openai):
        request = self.factory.post("/fortune/analyze/")
        request.user = MagicMock()
        request.user.is_authenticated = True

        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock(delta=MagicMock(content="DeepSeek Response"))]

        mock_client_inst = mock_openai.return_value
        mock_client_inst.chat.completions.create.return_value = [mock_chunk]

        response_text = "".join(generate_ai_response("Test Prompt", request))

        self.assertEqual(response_text, "DeepSeek Response")
        mock_openai.assert_called()
        self.assertEqual(mock_openai.call_args.kwargs["base_url"], "https://api.deepseek.com")

    @patch("fortune.views.OpenAI")
    @patch.dict(os.environ, {}, clear=True)
    def test_no_server_key_raises_missing_key_error(self, mock_openai):
        request = self.factory.post("/fortune/analyze/")
        request.user = MagicMock()
        request.user.is_authenticated = False

        with self.assertRaises(Exception) as context:
            list(generate_ai_response("Test Prompt", request))

        self.assertIn("API_KEY_MISSING", str(context.exception))
