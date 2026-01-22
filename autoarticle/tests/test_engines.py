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

    @skipIf(not os.path.exists(FONT_PATH), "Korean font not available for testing")
    def test_pdf_engine_generation(self):
        engine = PDFEngine("Warm & Playful", "Test School")
        engine.draw_cover()
        engine.add_article(self.article_data)
        output = engine.output(dest='S')
        self.assertTrue(len(output) > 0)
        self.assertIsInstance(output, bytearray)

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
