from django.test import TestCase, Client
from django.urls import reverse

class AutoArticleWizardTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_wizard_step1_render(self):
        response = self.client.get(reverse('autoarticle:create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "정보 입력")
        self.assertTemplateUsed(response, 'autoarticle/wizard/step1.html')

    def test_wizard_step1_to_step2_flow(self):
        """
        Step 1 submission should lead to Step 2 (AI Generating screen).
        This is EXPECTED TO FAIL (RED) if we are currently redirecting directly to Step 3.
        """
        payload = {
            'step': '1',
            'school_name': '테스트 초교',
            'grade': '1학년',
            'event_name': '테스트 행사',
            'location': '강당',
            'date': '2025-01-01',
            'tone': '따뜻하고 감성적인',
            'keywords': '재미있는 활동'
        }
        response = self.client.post(reverse('autoarticle:create'), data=payload, follow=True)
        
        # Verify it went to step 2 URL or session indicates step 2
        # current implementation might fail this if it jumps to step 3
        self.assertIn('step=2', response.request.get('QUERY_STRING', ''))
        self.assertContains(response, "Gemini가 기사를 작성하고 있습니다")
