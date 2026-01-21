from django.test import TestCase
from .models import GeneratedArticle
from django.utils import timezone
import datetime

class GeneratedArticleModelTest(TestCase):
    def test_expanded_fields(self):
        # Create an article with all the new fields we plan to add
        article = GeneratedArticle.objects.create(
            topic="Test Topic",
            grade="6학년",
            location="강당",
            event_date=datetime.date.today(),
            tone="따뜻한",
            keywords="키워드1, 키워드2",
            hashtags=["#테스트", "#해시태그"],
            images=["path/to/img1.jpg", "path/to/img2.jpg"],
            school_name="테스트 초등학교"
        )
        
        saved_article = GeneratedArticle.objects.get(id=article.id)
        self.assertEqual(saved_article.grade, "6학년")
        self.assertEqual(saved_article.location, "강당")
        self.assertEqual(saved_article.event_date, datetime.date.today())
        self.assertEqual(saved_article.tone, "따뜻한")
        self.assertEqual(saved_article.keywords, "키워드1, 키워드2")
        self.assertEqual(saved_article.hashtags, ["#테스트", "#해시태그"])
        self.assertEqual(saved_article.images, ["path/to/img1.jpg", "path/to/img2.jpg"])
        self.assertEqual(saved_article.school_name, "테스트 초등학교")
