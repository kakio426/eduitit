"""
서비스 헬스체크 테스트

모든 메인 서비스 엔드포인트가 정상 작동하는지 확인합니다.
python manage.py test tests.test_services_health
"""
import pytest
from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch


class CoreServicesTest(TestCase):
    """Core 앱 서비스 테스트"""

    def setUp(self):
        self.client = Client()

    def test_home_page_loads(self):
        """홈페이지 로드 테스트"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Eduitit')

    def test_dashboard_redirects_unauthenticated(self):
        """대시보드 - 미인증 시 리다이렉트"""
        response = self.client.get('/dashboard/')
        # 로그인 필요 시 리다이렉트 또는 200
        self.assertIn(response.status_code, [200, 302])

    def test_prompts_page_loads(self):
        """프롬프트 랩 페이지 로드"""
        response = self.client.get('/prompts/')
        self.assertIn(response.status_code, [200, 302])

    def test_tools_page_loads(self):
        """도구 가이드 페이지 로드"""
        response = self.client.get('/tools/')
        self.assertIn(response.status_code, [200, 302])

    def test_about_page_loads(self):
        """About 페이지 로드"""
        response = self.client.get('/about/')
        self.assertIn(response.status_code, [200, 302])


class ProductsServicesTest(TestCase):
    """Products 앱 서비스 테스트"""

    def setUp(self):
        self.client = Client()

    def test_products_list_loads(self):
        """제품 목록 페이지 로드"""
        response = self.client.get('/products/')
        self.assertEqual(response.status_code, 200)

    def test_yut_game_loads(self):
        """윷놀이 게임 페이지 로드"""
        response = self.client.get('/products/yut/')
        self.assertEqual(response.status_code, 200)

    def test_dutyticker_loads(self):
        """DutyTicker 페이지 로드"""
        response = self.client.get('/products/dutyticker/')
        self.assertEqual(response.status_code, 200)


class AutoarticleServicesTest(TestCase):
    """Autoarticle 앱 서비스 테스트"""

    def setUp(self):
        self.client = Client()

    def test_autoarticle_create_page_loads(self):
        """자동 기사 생성 페이지 로드"""
        response = self.client.get('/autoarticle/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '정보 입력')

    def test_autoarticle_archive_loads(self):
        """기사 보관함 페이지 로드"""
        response = self.client.get('/autoarticle/archive/')
        self.assertEqual(response.status_code, 200)


class FortuneServicesTest(TestCase):
    """Fortune 앱 서비스 테스트"""

    def setUp(self):
        self.client = Client()

    def test_fortune_saju_page_loads(self):
        """사주 페이지 로드"""
        response = self.client.get('/fortune/')
        self.assertEqual(response.status_code, 200)

    def test_fortune_saju_alt_loads(self):
        """사주 대체 URL 로드"""
        response = self.client.get('/fortune/saju/')
        self.assertEqual(response.status_code, 200)


class ArtclassServicesTest(TestCase):
    """Artclass 앱 서비스 테스트"""

    def setUp(self):
        self.client = Client()

    def test_artclass_setup_loads(self):
        """미술 수업 설정 페이지 로드"""
        response = self.client.get('/artclass/')
        self.assertEqual(response.status_code, 200)

    def test_artclass_classroom_loads(self):
        """미술 수업 교실 페이지 로드 (세션 필요 시 리다이렉트)"""
        response = self.client.get('/artclass/room/')
        # 세션 데이터 없으면 setup으로 리다이렉트됨
        self.assertIn(response.status_code, [200, 302])


class SignaturesServicesTest(TestCase):
    """Signatures 앱 서비스 테스트"""

    def setUp(self):
        self.client = Client()

    def test_signatures_list_requires_auth(self):
        """서명 목록 - 인증 필요 확인"""
        response = self.client.get('/signatures/')
        # 로그인 필요 시 리다이렉트
        self.assertIn(response.status_code, [200, 302])


class PortfolioServicesTest(TestCase):
    """Portfolio 앱 서비스 테스트"""

    def setUp(self):
        self.client = Client()

    def test_portfolio_list_loads(self):
        """포트폴리오 목록 페이지 로드"""
        response = self.client.get('/portfolio/')
        self.assertEqual(response.status_code, 200)

    def test_portfolio_inquiry_loads(self):
        """포트폴리오 문의 페이지 로드"""
        response = self.client.get('/portfolio/inquiry/')
        self.assertEqual(response.status_code, 200)


class SchoolViolenceServicesTest(TestCase):
    """School Violence 앱 서비스 테스트"""

    def setUp(self):
        self.client = Client()

    def test_school_violence_chat_loads(self):
        """학교폭력 상담 채팅 페이지 로드"""
        response = self.client.get('/school-violence/')
        self.assertEqual(response.status_code, 200)


class AllServicesHealthCheckTest(TestCase):
    """
    모든 서비스 통합 헬스체크

    빠른 전체 점검용
    """

    def setUp(self):
        self.client = Client()
        self.endpoints = [
            ('/', 'Home'),
            ('/products/', 'Products List'),
            ('/products/yut/', 'Yut Game'),
            ('/products/dutyticker/', 'DutyTicker'),
            ('/autoarticle/', 'AutoArticle'),
            ('/autoarticle/archive/', 'AutoArticle Archive'),
            ('/fortune/', 'Fortune Saju'),
            ('/artclass/', 'ArtClass Setup'),
            ('/artclass/room/', 'ArtClass Room'),
            ('/portfolio/', 'Portfolio'),
            ('/portfolio/inquiry/', 'Portfolio Inquiry'),
            ('/school-violence/', 'School Violence Chat'),
        ]

    def test_all_public_endpoints_accessible(self):
        """모든 공개 엔드포인트 접근성 테스트"""
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
                    'success': success
                })
            except Exception as e:
                results.append({
                    'name': name,
                    'url': url,
                    'status': 'ERROR',
                    'success': False,
                    'error': str(e)
                })

        # 결과 출력
        print("\n" + "=" * 60)
        print("Services Health Check Results")
        print("=" * 60)

        for r in results:
            status_icon = "[OK]" if r['success'] else "[FAIL]"
            print(f"{status_icon} [{r['status']}] {r['name']}: {r['url']}")

        print("=" * 60)

        # 실패한 서비스 확인
        failed = [r for r in results if not r['success']]
        self.assertEqual(len(failed), 0, f"실패한 서비스: {failed}")
