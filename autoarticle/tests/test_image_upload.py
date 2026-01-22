from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from autoarticle.models import GeneratedArticle
import os

class AutoArticleImageUploadTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')

    def test_step1_renders_file_input(self):
        """Test that Step 1 form renders file input with multiple attribute"""
        response = self.client.get(reverse('autoarticle:create'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check for file input with name 'images' and 'multiple' attribute
        # We check for various quote styles just in case
        self.assertTrue(
            'input type=\'file\'' in content or 'input type="file"' in content,
            "File input not found in template"
        )
        self.assertTrue(
            'name=\'images\'' in content or 'name="images"' in content,
            "Images input name not found"
        )
        self.assertTrue(
            'multiple' in content,
            "Multiple attribute missing from image input"
        )

    def test_image_upload_persistence(self):
        """Test that submitted images are saved in the session"""
        image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        img1 = SimpleUploadedFile("test1.png", image_content, content_type="image/png")
        img2 = SimpleUploadedFile("test2.png", image_content, content_type="image/png")

        data = {
            'step': '1',
            'grade': '1학년',
            'event_name': '테스트 행사',
            'keywords': '테스트 내용',
            'images': [img1, img2]
        }
        
        # We need to simulate the multi-step wizard. Step 1 POST should redirect to step 2.
        response = self.client.post(reverse('autoarticle:create'), data, follow=True)
        self.assertEqual(response.status_code, 200) 
        
        # Check session for saved image paths
        # Note: In TestCase, the session might be cleared or modified depending on how redirects are handled
        # But request.session['article_images'] should be there after step 1
        session = self.client.session
        self.assertIn('article_images', session, "Image paths not found in session")
        self.assertEqual(len(session['article_images']), 2)
        
        # Verify files actually exist on disk in the media location
        from django.conf import settings
        for path in session['article_images']:
            full_path = os.path.join(settings.MEDIA_ROOT, path)
            self.assertTrue(os.path.exists(full_path), f"File {full_path} was not created")
            # Cleanup
            if os.path.exists(full_path):
                # Ensure the file is closed before removing if possible, 
                # but usually it's fine in tests
                try:
                    os.remove(full_path)
                except:
                    pass

    def test_full_wizard_image_persistence(self):
        """Test that images uploaded in Step 1 are saved in the final GeneratedArticle model"""
        from unittest.mock import patch
        import datetime
        
        image_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        img = SimpleUploadedFile("test_persist.png", image_content, content_type="image/png")

        # Step 1: Upload with full data
        self.client.post(reverse('autoarticle:create'), {
            'step': '1',
            'school_name': 'Test School',
            'grade': '1학년',
            'event_name': 'Full Flow Test',
            'location': 'Test Location',
            'date': '2026-01-22',
            'tone': '정중한',
            'keywords': 'Testing persistence',
            'images': [img]
        }, follow=True)
        
        # Step 2: Skip AI generation (we'll manually set the session draft)
        input_data = self.client.session.get('article_input')
        images = self.client.session.get('article_images')
        
        self.assertIsNotNone(input_data, "Step 1 input_data missing from session")
        self.assertIsNotNone(images, "Step 1 images missing from session")
        
        # Set up a fake draft in the session
        draft = {
            'input_data': input_data,
            'title': 'Test Title',
            'content': 'Test Content',
            'hashtags': ['test'],
            'images': images,
            'original_generated_content': 'Test Content'
        }
        session = self.client.session
        session['article_draft'] = draft
        session.save()
        
        # Step 3: Save Article - Mock the AI services, RAG, and PPTEngine
        with patch('autoarticle.views.summarize_article_for_ppt') as mock_sum, \
             patch('autoarticle.views.ArticleCreateView.get_style_rag') as mock_rag, \
             patch('autoarticle.views.PPTEngine') as mock_ppt:
            mock_sum.return_value = ["Point 1", "Point 2", "Point 3"]
            mock_rag.return_value = None # Disable RAG for test
            
            # Mock ppt_engine.create_presentation to return a dummy BytesIO
            import io
            mock_ppt.return_value.create_presentation.return_value = io.BytesIO(b"fake ppt content")
            
            response = self.client.post(reverse('autoarticle:create'), {
                'step': '3',
                'title': 'Final Title',
                'content': 'Final Content',
                'hashtags': '#final #test'
            }, follow=True)

        
        if response.status_code == 302:
            print(f"DEBUG: Redirected to: {response.url}")
        
        if response.status_code != 200 and response.status_code != 302:
            print(f"DEBUG: Response status code: {response.status_code}")
            print(f"DEBUG: Response content: {response.content.decode()[:1000]}")

        # Verify model
        try:
            article = GeneratedArticle.objects.latest('id')
        except GeneratedArticle.DoesNotExist:
            print(f"DEBUG: Response content on failure: {response.content.decode()[:2000]}")
            self.fail("GeneratedArticle was not created")

        self.assertEqual(article.title, 'Final Title')


        self.assertEqual(len(article.images), 1)
        self.assertTrue('autoarticle/images/' in article.images[0])
        
        # Cleanup
        from django.conf import settings
        full_path = os.path.join(settings.MEDIA_ROOT, article.images[0])
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except:
                pass
