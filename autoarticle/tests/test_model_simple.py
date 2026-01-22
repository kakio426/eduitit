from django.test import TestCase
from autoarticle.models import GeneratedArticle
import datetime

class ModelTest(TestCase):
    def test_create_article_with_images(self):
        article = GeneratedArticle.objects.create(
            title="Test",
            images=["path/to/img1.png", "path/to/img2.png"],
            event_date=datetime.date.today()
        )
        self.assertEqual(len(article.images), 2)
        self.assertEqual(article.title, "Test")
