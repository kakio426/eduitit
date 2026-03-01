"""
Service health tests for key public endpoints.
Run with: python manage.py test tests.test_services_health
"""

import json
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from artclass.models import ArtClass


class CoreServicesTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Eduitit')

    def test_dashboard_redirects_unauthenticated(self):
        response = self.client.get('/dashboard/')
        self.assertIn(response.status_code, [200, 302])

    def test_prompts_page_loads(self):
        response = self.client.get('/prompts/')
        self.assertIn(response.status_code, [200, 302])

    def test_tools_page_loads(self):
        response = self.client.get('/tools/')
        self.assertIn(response.status_code, [200, 302])

    def test_about_page_loads(self):
        response = self.client.get('/about/')
        self.assertIn(response.status_code, [200, 302])


class ProductsServicesTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_products_list_loads(self):
        response = self.client.get('/products/')
        self.assertEqual(response.status_code, 200)

    def test_yut_game_loads(self):
        response = self.client.get('/products/yut/')
        self.assertEqual(response.status_code, 200)

    def test_dutyticker_loads(self):
        response = self.client.get('/products/dutyticker/')
        self.assertEqual(response.status_code, 200)


class AutoarticleServicesTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_autoarticle_create_page_loads(self):
        response = self.client.get('/autoarticle/')
        self.assertIn(response.status_code, [200, 302])

    def test_autoarticle_archive_loads(self):
        response = self.client.get('/autoarticle/archive/')
        self.assertIn(response.status_code, [200, 302])


class FortuneServicesTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_fortune_saju_page_loads(self):
        response = self.client.get('/fortune/')
        self.assertIn(response.status_code, [200, 302])

    def test_fortune_saju_alt_loads(self):
        response = self.client.get('/fortune/saju/')
        self.assertIn(response.status_code, [200, 302])

    def test_daily_fortune_api_requires_post(self):
        response = self.client.get('/fortune/api/daily/')
        self.assertEqual(response.status_code, 405)

    def test_daily_fortune_api_invalid_json_returns_400(self):
        response = self.client.post(
            '/fortune/api/daily/',
            data='not-json',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_daily_fortune_api_valid_json_authenticated_returns_200(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='fortune_daily_api_user',
            email='fortune_daily_api_user@example.com',
            password='pw123456',
        )
        self.client.force_login(user)

        payload = {
            'target_date': '2026-03-10',
            'natal_chart': {},
            'name': '테스트 선생님',
            'gender': 'female',
            'mode': 'teacher',
        }

        with patch('fortune.views._check_saju_ratelimit', new=AsyncMock(return_value=False)):
            with patch('fortune.views.calculator.get_pillars', return_value={}):
                with patch('fortune.prompts.get_daily_fortune_prompt', return_value='mock prompt'):
                    collect_mock = AsyncMock(return_value='mock daily fortune result')
                    with patch('fortune.views._collect_ai_response_async', new=collect_mock):
                        response = self.client.post(
                            '/fortune/api/daily/',
                            data=json.dumps(payload),
                            content_type='application/json',
                        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body.get('success'))
        self.assertEqual(body.get('target_date'), payload['target_date'])
        self.assertEqual(body.get('result'), 'mock daily fortune result')
        collect_mock.assert_awaited()


class ReservationsServicesTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_reservations_root_loads(self):
        response = self.client.get('/reservations/')
        self.assertIn(response.status_code, [200, 302])


class ArtclassServicesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.art_class = ArtClass.objects.create(
            title='Test Art Class',
            youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            default_interval=10,
        )

    def test_artclass_setup_loads(self):
        response = self.client.get('/artclass/')
        self.assertEqual(response.status_code, 200)

    def test_artclass_classroom_loads(self):
        response = self.client.get(f'/artclass/classroom/{self.art_class.pk}/')
        self.assertEqual(response.status_code, 200)


class SignaturesServicesTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_signatures_list_requires_auth(self):
        response = self.client.get('/signatures/')
        self.assertIn(response.status_code, [200, 302])


class PortfolioServicesTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_portfolio_list_loads(self):
        response = self.client.get('/portfolio/')
        self.assertEqual(response.status_code, 200)

    def test_portfolio_inquiry_loads(self):
        response = self.client.get('/portfolio/inquiry/')
        self.assertEqual(response.status_code, 200)


class AllServicesHealthCheckTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.art_class = ArtClass.objects.create(
            title='Health Test Art Class',
            youtube_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            default_interval=10,
        )
        self.endpoints = [
            ('/', 'Home'),
            ('/products/', 'Products List'),
            ('/products/yut/', 'Yut Game'),
            ('/products/dutyticker/', 'DutyTicker'),
            ('/autoarticle/', 'AutoArticle'),
            ('/autoarticle/archive/', 'AutoArticle Archive'),
            ('/fortune/', 'Fortune Saju'),
            ('/artclass/', 'ArtClass Setup'),
            (f'/artclass/classroom/{self.art_class.pk}/', 'ArtClass Room'),
            ('/portfolio/', 'Portfolio'),
            ('/portfolio/inquiry/', 'Portfolio Inquiry'),
        ]

    def test_all_public_endpoints_accessible(self):
        results = []

        for url, name in self.endpoints:
            try:
                response = self.client.get(url)
                status = response.status_code
                success = status in [200, 302]
                results.append({
                    'name': name,
                    'url': url,
                    'status': status,
                    'success': success,
                })
            except Exception as e:
                results.append({
                    'name': name,
                    'url': url,
                    'status': 'ERROR',
                    'success': False,
                    'error': str(e),
                })

        print("\n" + "=" * 60)
        print("Services Health Check Results")
        print("=" * 60)
        for item in results:
            status_icon = "[OK]" if item['success'] else "[FAIL]"
            print(f"{status_icon} [{item['status']}] {item['name']}: {item['url']}")
        print("=" * 60)

        failed = [item for item in results if not item['success']]
        self.assertEqual(len(failed), 0, f"Failed services: {failed}")
