from django.test import SimpleTestCase
from fortune.utils.chat_ai import _strip_markdown_chars


class TestChatAI(SimpleTestCase):
    def test_strip_markdown_chars(self):
        raw = "**bold** # title > quote [x] _em_ `code`"
        cleaned = _strip_markdown_chars(raw)
        self.assertEqual(cleaned, "bold  title  quote x em code")

    def test_strip_markdown_chars_keeps_plain_text(self):
        raw = "안녕하세요 오늘 운세를 알려드릴게요."
        cleaned = _strip_markdown_chars(raw)
        self.assertEqual(cleaned, raw)

class TestChatAISanitize(SimpleTestCase):
    def test_sanitize_stream_chunk_escapes_html(self):
        from fortune.utils.chat_ai import _sanitize_stream_chunk

        raw = "<script>alert(1)</script>\nline2"
        cleaned = _sanitize_stream_chunk(raw)
        self.assertEqual(cleaned, "scriptalert(1)/script<br>line2")
