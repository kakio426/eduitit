import io
import os
from unittest import skipIf
from django.test import TestCase
from autoarticle.engines.pdf_engine import PDFEngine
from autoarticle.engines.ppt_engine import PPTEngine
from autoarticle.engines.word_engine import WordEngine
from autoarticle.engines.constants import FONT_PATH

class DocumentEnginesTest(TestCase):
    def setUp(self):
        self.article_data = {
            'title': 'Test Title',
            'content': 'This is test content.',
            'date': '2025.01.01',
            'location': 'Test Location',
            'grade': 'All Grades',
            'images': '[]'
        }

    def test_pdf_engine_generation(self):
        """Test PDF generation. If Korean font is not available, test with ASCII-only content."""
        engine = PDFEngine("Warm & Playful", "Test School")

        # Only draw cover if font is available (cover contains Korean text)
        if engine.font_available:
            engine.draw_cover()
        else:
            # For ASCII-only testing, just add a page without cover
            engine.add_page()

        engine.add_article(self.article_data)
        output = engine.output(dest='S')
        self.assertTrue(len(output) > 0)
        # Check if it's a valid PDF (starts with %PDF)
        if isinstance(output, str):
            self.assertTrue(output.startswith('%PDF'))
        elif isinstance(output, (bytes, bytearray)):
            self.assertTrue(output.startswith(b'%PDF'))

    def test_ppt_engine_generation(self):
        engine = PPTEngine("Cool & Modern", "Test School")
        # Format for PPT create_presentation is a list of dicts
        ppt_data = {
            'title': self.article_data['title'],
            'content': [self.article_data['content']],
            'date': self.article_data['date'],
            'location': self.article_data['location'],
            'images': []
        }
        buffer = engine.create_presentation([ppt_data])
        self.assertTrue(buffer.getvalue())
        self.assertIsInstance(buffer, io.BytesIO)

    def test_word_engine_generation(self):
        engine = WordEngine("Pastel & Soft", "Test School")
        buffer = engine.generate([self.article_data])
        self.assertTrue(buffer.getvalue())
        self.assertIsInstance(buffer, io.BytesIO)
