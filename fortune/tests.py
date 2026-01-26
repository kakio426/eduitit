from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import FortuneResult

class FortuneDetailTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='owner', password='password')
        self.other_user = User.objects.create_user(username='other', password='password')
        self.fortune = FortuneResult.objects.create(
            user=self.user,
            mode='teacher',
            natal_chart={'day': '갑자'},
            result_text='테스트 결과'
        )

    def test_detail_view_owner_access(self):
        self.client.login(username='owner', password='password')
        response = self.client.get(f'/fortune/history/{self.fortune.id}/')
        self.assertEqual(response.status_code, 200)

    def test_detail_view_other_access(self):
        self.client.login(username='other', password='password')
        response = self.client.get(f'/fortune/history/{self.fortune.id}/')
        self.assertNotEqual(response.status_code, 200)  # Should be 404 or 403
