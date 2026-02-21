from django.test import TestCase
from .models import Insight

class InsightModelTest(TestCase):
    def test_create_devlog_insight(self):
        """Test creating a DevLog insight"""
        # This will fail initially because 'category' field doesn't exist
        insight = Insight.objects.create(
            title="My First DevLog",
            content="```python\nprint('hello')\n```",
            category="devlog",
            video_url="https://youtube.com", # Required field currently
        )
        self.assertEqual(insight.category, "devlog")

    def test_insight_detail_view(self):
        insight = Insight.objects.create(
            title="Detail Test",
            content="Content",
            category="devlog"
        )
        from django.urls import reverse
        # Assuming URL pattern name 'insights:detail' and pk
        response = self.client.get(reverse('insights:detail', args=[insight.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'insights/insight_detail.html')

    def test_legacy_singular_path_redirects_to_list(self):
        response = self.client.get('/insight/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'insights/insight_list.html')
