import html

from django.test import TestCase, override_settings
from django.urls import reverse

from core.guide_links import SERVICE_GUIDE_PADLET_URL
from core.seo import DEFAULT_HOME_DESCRIPTION
from insights.models import Insight
from products.models import Product, ServiceManual


@override_settings(HOME_V2_ENABLED=True)
class SeoFoundationTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title="미술 수업 도우미",
            description="유튜브 기반 수업 흐름을 빠르게 정리합니다.",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="artclass:setup",
            solve_text="수업 흐름과 단계 안내를 한 번에 정리합니다.",
        )
        self.manual = ServiceManual.objects.create(
            product=self.product,
            title="미술 수업 도우미 시작하기",
            description="바로 열고 바로 단계 준비하는 흐름을 안내합니다.",
            is_published=True,
        )
        self.sensitive_product = Product.objects.create(
            title="학급 캘린더",
            description="학급 일정을 빠르게 정리합니다.",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="classcalendar:main",
            solve_text="오늘 일정과 주간 흐름을 한 번에 정리합니다.",
        )
        self.sensitive_manual = ServiceManual.objects.create(
            product=self.sensitive_product,
            title="학급 캘린더 시작하기",
            description="바로 열고 바로 일정 등록하는 흐름을 안내합니다.",
            is_published=True,
        )
        self.insight = Insight.objects.create(
            title="교실 AI 운영 팁",
            content="수업과 행정에 바로 쓸 수 있는 짧은 운영 팁을 정리했습니다.",
            category="column",
            thumbnail_url="https://eduitit.site/static/images/test-thumb.png",
            tags="#AI,#교실",
        )

    def test_robots_txt_only_exposes_sitemap_without_internal_hints(self):
        response = self.client.get("/robots.txt")
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sitemap: https://eduitit.site/sitemap.xml", content)
        self.assertNotIn("/admin/", content)
        self.assertNotIn("/accounts/", content)
        self.assertNotIn("/secret-admin-kakio/", content)
        self.assertNotIn("*/create/", content)
        self.assertNotIn("*/edit/", content)

    def test_sitemap_xml_excludes_guide_redirect_routes_and_lists_public_product_pages(self):
        response = self.client.get("/sitemap.xml")
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn(reverse("home"), content)
        self.assertIn(reverse("insights:list"), content)
        self.assertIn(reverse("product_detail", kwargs={"pk": self.product.pk}), content)
        self.assertIn(reverse("insights:detail", kwargs={"pk": self.insight.pk}), content)
        self.assertIn(reverse("noticegen:main"), content)
        self.assertIn(reverse("qrgen:landing"), content)
        self.assertNotIn(reverse("tool_guide"), content)
        self.assertNotIn(reverse("service_guide_list"), content)
        self.assertNotIn(reverse("service_guide_detail", kwargs={"pk": self.manual.pk}), content)
        self.assertNotIn(reverse("service_guide_detail", kwargs={"pk": self.sensitive_manual.pk}), content)
        self.assertNotIn(reverse("product_detail", kwargs={"pk": self.sensitive_product.pk}), content)
        self.assertNotIn("/secret-admin-kakio/", content)
        self.assertNotIn(reverse("insights:create"), content)
        self.assertNotIn("/api/", content)

    def test_home_page_uses_fixed_canonical_and_og_url(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<link rel="canonical" href="https://eduitit.site/">', content)
        self.assertIn('<meta property="og:url" content="https://eduitit.site/">', content)
        self.assertIn("<title>교사를 위한 AI·학급 운영 도구 | Eduitit</title>", content)
        self.assertIn('<link rel="icon" href="/favicon.ico" sizes="any">', content)
        self.assertIn('"@type":"WebSite"', content)
        self.assertIn('"@type":"CollectionPage"', content)

    def test_favicon_ico_route_returns_icon_response(self):
        response = self.client.get("/favicon.ico")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("image/"))
        self.assertIn("public, max-age=604800, immutable", response["Cache-Control"])

    def test_insight_list_filtered_query_uses_canonical_root_and_noindex(self):
        response = self.client.get(f"{reverse('insights:list')}?tag=AI")
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<link rel="canonical" href="https://eduitit.site/insights/">', content)
        self.assertIn('<meta name="robots" content="noindex,follow">', content)

    def test_insight_detail_uses_article_meta_and_extra_head_assets(self):
        response = self.client.get(reverse("insights:detail", args=[self.insight.pk]))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>교실 AI 운영 팁 - Insight Library</title>", content)
        self.assertIn('<meta property="og:type" content="article">', content)
        self.assertIn('https://eduitit.site/insights/', content)
        self.assertIn("test-thumb.png", content)
        self.assertIn("prism-tomorrow.min.css", content)
        self.assertIn('"@type":"Article"', content)
        self.assertIn('"@type":"BreadcrumbList"', content)

    def test_public_tool_and_app_pages_get_page_specific_meta(self):
        cases = (
            ("prompt_lab", "AI 프롬프트 레시피 | Eduitit", "https://eduitit.site/prompts/"),
            ("noticegen:main", "알림장·주간학습 멘트 생성기 | Eduitit", "https://eduitit.site/noticegen/"),
            ("qrgen:landing", "수업 QR 생성기 | Eduitit", "https://eduitit.site/qrgen/"),
        )

        for route_name, title, canonical in cases:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                content = response.content.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"<title>{html.escape(title)}</title>", content)
                self.assertIn(f'<link rel="canonical" href="{canonical}">', content)
                self.assertIn(f'<meta property="og:url" content="{canonical}">', content)

    def test_guide_routes_redirect_to_padlet(self):
        cases = (
            reverse("tool_guide"),
            reverse("service_guide_list"),
            reverse("service_guide_detail", kwargs={"pk": self.manual.pk}),
            reverse("service_guide_detail", kwargs={"pk": self.sensitive_manual.pk}),
        )

        for path in cases:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], SERVICE_GUIDE_PADLET_URL)

    def test_public_landing_pages_get_unique_meta(self):
        cases = (
            ("product_list", "교사용 서비스 카탈로그 | Eduitit", "https://eduitit.site/products/", "수업 준비, 학급 운영, 문서 작성, 활동 도구를 상황별로 정리한 Eduitit 서비스 카탈로그입니다."),
            ("portfolio:list", "AI 연수·협업 포트폴리오 | Eduitit", "https://eduitit.site/portfolio/", "AI 활용 연수, 에듀테크 설계, 교실 적용 사례와 협업 제안을 한 곳에서 확인하는 포트폴리오입니다."),
            ("insights:list", "교실 AI 인사이트 | Eduitit", "https://eduitit.site/insights/", "수업, 학급 운영, AI 활용에 도움이 되는 실전 인사이트를 교사 관점으로 정리했습니다."),
            ("about", "Eduitit 소개 | 교사의 스마트한 하루", "https://eduitit.site/about/", "교사의 시간을 아껴 주는 도구를 왜, 어떻게 만들고 있는지 Eduitit의 방향과 철학을 소개합니다."),
        )

        for route_name, title, canonical, description in cases:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                content = response.content.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"<title>{html.escape(title)}</title>", content)
                self.assertIn(f'<link rel="canonical" href="{canonical}">', content)
                self.assertIn(f'<meta property="og:url" content="{canonical}">', content)
                self.assertIn(html.escape(description), content)
                self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_auth_pages_use_noindex_and_specific_meta(self):
        cases = (
            ("account_login", "로그인 | Eduitit", "https://eduitit.site/accounts/login/", "에듀이티잇에 로그인하고 교실 운영, 알림장 작성, 서비스 가이드를 이어서 사용하세요."),
            ("account_signup", "회원가입 | Eduitit", "https://eduitit.site/accounts/signup/", "에듀이티잇 계정으로 교사를 위한 AI·학급 운영 도구를 바로 시작하세요."),
        )

        for route_name, title, canonical, description in cases:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                content = response.content.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"<title>{html.escape(title)}</title>", content)
                self.assertIn(f'<meta name="robots" content="noindex,nofollow">', content)
                self.assertIn(f'<link rel="canonical" href="{canonical}">', content)
                self.assertIn(f'<meta property="og:url" content="{canonical}">', content)
                self.assertIn(html.escape(description), content)
                self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_product_detail_uses_specific_meta(self):
        product_response = self.client.get(reverse("product_detail", kwargs={"pk": self.product.pk}))
        product_content = product_response.content.decode("utf-8")

        self.assertEqual(product_response.status_code, 200)
        self.assertIn("<title>미술 수업 도우미 - Eduitit</title>", product_content)
        self.assertIn(
            f'<link rel="canonical" href="https://eduitit.site{reverse("product_detail", kwargs={"pk": self.product.pk})}">',
            product_content,
        )
        self.assertIn("수업 흐름과 단계 안내를 한 번에 정리합니다.", product_content)
        self.assertIn('"@type":"Article"', product_content)
        self.assertIn('"@type":"BreadcrumbList"', product_content)

    def test_sensitive_product_uses_noindex_headers(self):
        product_response = self.client.get(reverse("product_detail", kwargs={"pk": self.sensitive_product.pk}))
        product_content = product_response.content.decode("utf-8")

        self.assertEqual(product_response.status_code, 200)
        self.assertIn('<meta name="robots" content="noindex,nofollow">', product_content)
        self.assertEqual(product_response["X-Robots-Tag"], "noindex, nofollow")
