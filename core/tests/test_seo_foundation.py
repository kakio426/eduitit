import html

from django.test import TestCase, override_settings
from django.urls import reverse

from insights.models import Insight
from products.models import Product, ServiceManual


@override_settings(HOME_V2_ENABLED=True)
class SeoFoundationTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title="학급 캘린더",
            description="학급 일정을 빠르게 정리합니다.",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="classcalendar:main",
            solve_text="오늘 일정과 주간 흐름을 한 번에 정리합니다.",
        )
        self.manual = ServiceManual.objects.create(
            product=self.product,
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

    def test_robots_txt_exposes_sitemap_and_major_disallow_rules(self):
        response = self.client.get("/robots.txt")
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Sitemap: https://eduitit.site/sitemap.xml", content)
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Disallow: /accounts/", content)
        self.assertIn("Disallow: /api/", content)
        self.assertIn("Disallow: */create/", content)

    def test_sitemap_xml_lists_public_home_manual_product_insight_and_tools(self):
        response = self.client.get("/sitemap.xml")
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn(reverse("home"), content)
        self.assertIn(reverse("insights:list"), content)
        self.assertIn(reverse("service_guide_list"), content)
        self.assertIn(reverse("service_guide_detail", kwargs={"pk": self.manual.pk}), content)
        self.assertIn(reverse("product_detail", kwargs={"pk": self.product.pk}), content)
        self.assertIn(reverse("insights:detail", kwargs={"pk": self.insight.pk}), content)
        self.assertIn(reverse("noticegen:main"), content)
        self.assertIn(reverse("qrgen:landing"), content)
        self.assertNotIn("/secret-admin-kakio/", content)
        self.assertNotIn(reverse("insights:create"), content)
        self.assertNotIn("/api/", content)

    def test_home_page_uses_fixed_canonical_and_og_url(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<link rel="canonical" href="https://eduitit.site/">', content)
        self.assertIn('<meta property="og:url" content="https://eduitit.site/">', content)
        self.assertIn("<title>Eduitit - 선생님의 스마트한 하루</title>", content)

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

    def test_public_tool_and_reference_pages_get_page_specific_meta(self):
        cases = (
            ("prompt_lab", "AI 프롬프트 레시피 - Eduitit", "https://eduitit.site/prompts/"),
            ("tool_guide", "도구 가이드 - Eduitit", "https://eduitit.site/tools/"),
            ("service_guide_list", "서비스 가이드 - Eduitit", "https://eduitit.site/manuals/"),
            ("noticegen:main", "알림장 & 주간학습 멘트 생성기 - Eduitit", "https://eduitit.site/noticegen/"),
            ("qrgen:landing", "수업 QR 생성기 - Eduitit", "https://eduitit.site/qrgen/"),
        )

        for route_name, title, canonical in cases:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                content = response.content.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"<title>{html.escape(title)}</title>", content)
                self.assertIn(f'<link rel="canonical" href="{canonical}">', content)
                self.assertIn(f'<meta property="og:url" content="{canonical}">', content)

    def test_service_guide_and_product_detail_use_specific_meta(self):
        manual_response = self.client.get(reverse("service_guide_detail", kwargs={"pk": self.manual.pk}))
        manual_content = manual_response.content.decode("utf-8")
        product_response = self.client.get(reverse("product_detail", kwargs={"pk": self.product.pk}))
        product_content = product_response.content.decode("utf-8")

        self.assertEqual(manual_response.status_code, 200)
        self.assertIn("<title>학급 캘린더 시작하기 - 서비스 가이드 - Eduitit</title>", manual_content)
        self.assertIn(
            f'<link rel="canonical" href="https://eduitit.site{reverse("service_guide_detail", kwargs={"pk": self.manual.pk})}">',
            manual_content,
        )
        self.assertIn("바로 열고 바로 일정 등록하는 흐름", manual_content)

        self.assertEqual(product_response.status_code, 200)
        self.assertIn("<title>학급 캘린더 - Eduitit</title>", product_content)
        self.assertIn(
            f'<link rel="canonical" href="https://eduitit.site{reverse("product_detail", kwargs={"pk": self.product.pk})}">',
            product_content,
        )
        self.assertIn("오늘 일정과 주간 흐름을 한 번에 정리합니다.", product_content)
