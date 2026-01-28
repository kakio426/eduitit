from django.test import TestCase, RequestFactory
from django.urls import reverse
from autoarticle.views import ArticleCreateView
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware

class DirectUploadTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = ArticleCreateView.as_view()

    def test_post_step1_with_image_urls(self):
        """
        RED PHASE: This test verifies that Step 1 can receive Cloudinary URLs from the client.
        Current implementation only handles FILES, so this will either fail to save URLs or error.
        """
        from django.http import QueryDict
        from django.urls import reverse
        url = reverse('autoarticle:create')
        data = QueryDict(mutable=True)
        data.update({
            'step': '1',
            'school_name': 'Test School',
            'event_name': 'Test Event',
            'keywords': 'test, keywords',
        })
        data.appendlist('image_urls', 'https://res.cloudinary.com/demo/image/upload/v1/test1.jpg')
        data.appendlist('image_urls', 'https://res.cloudinary.com/demo/image/upload/v2/test2.jpg')
        
        request = self.factory.post(url, data)
        
        # Add session and messages middleware manually for RequestFactory
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        
        msg_middleware = MessageMiddleware(lambda r: None)
        msg_middleware.process_request(request)

        response = self.view(request)
        
        # We expect a redirect to Step 2
        self.assertEqual(response.status_code, 302, f"Expected 302, got {response.status_code}. Content: {getattr(response, 'content', b'')[:200]}")
        
        # CHECK: The image URLs should be in the session
        # (This is expected to fail with the current code)
        saved_images = request.session.get('article_images', [])
        self.assertIn('https://res.cloudinary.com/demo/image/upload/v1/test1.jpg', saved_images)
        self.assertEqual(len(saved_images), 2)
