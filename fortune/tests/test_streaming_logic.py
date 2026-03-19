from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch
from fortune.views import generate_ai_response


class AIStreamingTestCase(SimpleTestCase):
    @patch('fortune.views.OpenAI')
    def test_generate_ai_response_streaming_type(self, mock_openai_class):
        """
        GREEN PHASE: Should succeed because generate_ai_response now yields chunks.
        """
        mock_request = MagicMock()
        mock_request.user.is_authenticated = False

        with patch('os.environ.get', return_value="fake-deepseek-key"):
            mock_client = mock_openai_class.return_value
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock(delta=MagicMock(content="Test Response"))]
            mock_client.chat.completions.create.return_value = [mock_chunk]

            result = generate_ai_response("Test Prompt", mock_request)

            assert hasattr(result, '__iter__'), "Result should be an iterator for streaming"
            assert not isinstance(result, (str, bytes)), "Result should not be a plain string"

    @patch('fortune.views.OpenAI')
    def test_generate_ai_response_streaming_content(self, mock_openai_class):
        """
        Verify that iterating over the result yields chunks.
        """
        mock_request = MagicMock()
        mock_request.user.is_authenticated = False

        with patch('os.environ.get', return_value="fake-deepseek-key"):
            mock_client = mock_openai_class.return_value

            chunk1 = MagicMock()
            chunk1.choices = [MagicMock(delta=MagicMock(content="Part 1 "))]
            chunk2 = MagicMock()
            chunk2.choices = [MagicMock(delta=MagicMock(content="Part 2"))]

            mock_client.chat.completions.create.return_value = [chunk1, chunk2]

            result = generate_ai_response("Test Prompt", mock_request)
            chunks = list(result)
            assert len(chunks) == 2
            assert "".join(chunks) == "Part 1 Part 2"
