import unittest
import shutil
import tempfile
import os
from django.test import TestCase

try:
    import chromadb
    CHROMA_INSTALLED = True
except ImportError:
    CHROMA_INSTALLED = False

from autoarticle.engines.rag_service import StyleRAGService

@unittest.skipIf(not CHROMA_INSTALLED, "ChromaDB not installed")
class StyleRAGServiceTest(TestCase):
    def setUp(self):
        # Create a temporary directory for ChromaDB
        self.test_dir = tempfile.mkdtemp()
        self.rag = StyleRAGService(persist_directory=self.test_dir)

    def tearDown(self):
        # Cleanup temporary directory
        shutil.rmtree(self.test_dir)

    def test_learn_style_and_retrieve(self):
        # 1. Learn a style correction
        original = "The students was happy."
        corrected = "The students were happy."
        
        self.rag.learn_style(
            original_text=original,
            corrected_text=corrected,
            user_id=1,
            tags="grammar"
        )
        
        # 2. Retrieve using similar text
        query = "The teachers was happy."
        results = self.rag.retrieve_style_examples(query_text=query, n_results=1)
        
        # 3. Verify something is returned
        # Note: Semantic similarity might vary, but we check structure
        self.assertTrue(len(results) > 0)
        self.assertIn('original', results[0])
        self.assertIn('corrected', results[0])
        
        # Check if the retrieved correction is indeed the one we stored
        self.assertEqual(results[0]['corrected'], corrected)
