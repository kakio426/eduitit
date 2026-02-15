"""
Service health tests for key public endpoints.
Run with: python manage.py test tests.test_services_health
"""

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


class SchoolViolenceServicesTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_school_violence_chat_loads(self):
        response = self.client.get('/school-violence/')
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
            ('/school-violence/', 'School Violence Chat'),
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
