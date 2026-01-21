from django.test import TestCase
from django.urls import reverse

class AboutPageTest(TestCase):
    def test_about_page_status(self):
        url = reverse('about')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/about.html')
