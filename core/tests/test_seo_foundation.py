import html

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from collect.models import CollectionRequest
from core.context_processors import seo_meta
from core.guide_links import SERVICE_GUIDE_PADLET_URL
from core.seo import DEFAULT_HOME_DESCRIPTION
from insights.models import Insight
from products.models import Product, ServiceManual
from schoolprograms.models import ProgramListing, ProviderProfile


@override_settings(HOME_V2_ENABLED=True)
class SeoFoundationTests(TestCase):
    def setUp(self):
        self.request_factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="seo-user",
            email="seo-user@example.com",
            password="test-pass-123",
        )
        self.user.userprofile.nickname = "SEO교사"
        self.user.userprofile.save(update_fields=["nickname"])
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
        self.collect_service = Product.objects.create(
            title="간편 수합",
            description="QR 또는 입장코드로 파일, 링크, 텍스트, 선택형 응답을 빠르게 모읍니다.",
            price=0,
            is_active=True,
            service_type="collect_sign",
            launch_route_name="collect:landing",
            solve_text="자료와 의견을 빠르게 모읍니다.",
        )
        self.handoff_service = Product.objects.create(
            title="배부 체크",
            description="명단을 저장해 두고 배부할 때 수령 여부를 빠르게 체크합니다.",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="handoff:landing",
            solve_text="배부 여부를 빠르게 기록합니다.",
        )
        self.noticegen_service = Product.objects.create(
            title="알림장 멘트 생성기",
            description="가정통신문과 알림장 멘트를 빠르게 만듭니다.",
            price=0,
            is_active=True,
            service_type="work",
            launch_route_name="noticegen:main",
            solve_text="전달 내용을 교사용 문장으로 정리합니다.",
        )
        self.schoolprograms_service = Product.objects.create(
            title="학교 체험·행사 찾기",
            description="학교로 찾아오는 프로그램을 지역과 주제로 비교합니다.",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="schoolprograms:landing",
            solve_text="학교 프로그램을 비교하고 바로 문의합니다.",
        )
        self.provider_user = get_user_model().objects.create_user(
            username="provider-user",
            email="provider@example.com",
            password="test-pass-123",
        )
        self.schoolprogram_provider = ProviderProfile.objects.create(
            user=self.provider_user,
            provider_name="상상체험 교육연구소",
            summary="찾아오는 과학 체험과 교사연수를 운영합니다.",
            description="학교 방문형 과학 체험학습과 교사 연수를 함께 운영하는 프로그램 업체입니다.",
            contact_email="hello@example.com",
            contact_phone="02-1234-5678",
            website="https://example.com/programs",
            service_area_summary="서울 · 경기",
        )
        self.schoolprogram_listing = ProgramListing.objects.create(
            provider=self.schoolprogram_provider,
            title="찾아오는 과학 실험 교실",
            summary="교실에서 바로 진행하는 안전한 과학 실험 체험입니다.",
            description="학교로 찾아가 학급 단위로 운영하는 과학 실험 체험 프로그램입니다.",
            category=ProgramListing.Category.FIELDTRIP,
            theme_tags=["과학", "실험"],
            grade_bands=["elementary_high", "middle"],
            delivery_mode=ProgramListing.DeliveryMode.VISITING,
            province="seoul",
            city="강남구",
            coverage_note="경기 일부 방문 가능",
            duration_text="90분",
            capacity_text="학급당 30명",
            price_text="학급당 30만원",
            safety_info="체험 강사 배상 책임 보험에 가입되어 있습니다.",
            materials_info="교실 책상 배치만 준비해 주세요.",
            faq="우천 시에도 실내에서 운영 가능합니다.",
            approval_status=ProgramListing.ApprovalStatus.APPROVED,
            published_at=timezone.now(),
        )
        self.collect_request = CollectionRequest.objects.create(
            creator=self.user,
            title="과학 실험 보고서",
            description="실험 사진과 관찰 기록을 제출해 주세요.",
            allow_file=True,
            allow_link=True,
            allow_text=True,
        )
        self.insight = Insight.objects.create(
            title="교실 AI 운영 팁",
            content="수업과 행정에 바로 쓸 수 있는 짧은 운영 팁을 정리했습니다.",
            category="column",
            thumbnail_url="https://eduitit.site/static/images/test-thumb.png",
            tags="#AI,#교실",
        )

    def test_context_processor_exposes_default_fallback_keys_only(self):
        context = seo_meta(self.request_factory.get("/ocrdesk/"))

        self.assertIn("default_page_title", context)
        self.assertIn("default_canonical_url", context)
        self.assertIn("default_og_title", context)
        self.assertIn("default_meta_description", context)
        self.assertEqual(context["default_canonical_url"], "https://eduitit.site/ocrdesk/")
        self.assertNotIn("page_title", context)
        self.assertNotIn("meta_description", context)
        self.assertNotIn("canonical_url", context)
        self.assertNotIn("og_title", context)
        self.assertNotIn("og_description", context)
        self.assertNotIn("robots", context)

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
        self.assertIn(reverse("about"), content)
        self.assertIn(reverse("product_list"), content)
        self.assertIn(reverse("portfolio:list"), content)
        self.assertIn(reverse("insights:list"), content)
        self.assertIn(reverse("prompt_lab"), content)
        self.assertIn(reverse("noticegen:main"), content)
        self.assertIn(reverse("qrgen:landing"), content)
        self.assertIn(reverse("collect:landing"), content)
        self.assertIn(reverse("handoff:landing"), content)
        self.assertIn(reverse("schoolprograms:landing"), content)
        self.assertIn(reverse("schoolprograms:listing_detail", args=[self.schoolprogram_listing.slug]), content)
        self.assertIn(reverse("schoolprograms:provider_detail", args=[self.schoolprogram_provider.slug]), content)
        self.assertIn(reverse("tts_announce"), content)
        self.assertIn(reverse("product_detail", kwargs={"pk": self.product.pk}), content)
        self.assertIn(reverse("insights:detail", kwargs={"pk": self.insight.pk}), content)
        self.assertNotIn(reverse("tool_guide"), content)
        self.assertNotIn(reverse("service_guide_list"), content)
        self.assertNotIn(reverse("service_guide_detail", kwargs={"pk": self.manual.pk}), content)
        self.assertNotIn(reverse("service_guide_detail", kwargs={"pk": self.sensitive_manual.pk}), content)
        self.assertNotIn(reverse("product_detail", kwargs={"pk": self.sensitive_product.pk}), content)
        self.assertNotIn(reverse("product_detail", kwargs={"pk": self.collect_service.pk}), content)
        self.assertNotIn(reverse("product_detail", kwargs={"pk": self.handoff_service.pk}), content)
        self.assertNotIn(reverse("product_detail", kwargs={"pk": self.noticegen_service.pk}), content)
        self.assertNotIn(reverse("product_detail", kwargs={"pk": self.schoolprograms_service.pk}), content)
        self.assertNotIn("/secret-admin-kakio/", content)
        self.assertNotIn(reverse("insights:create"), content)
        self.assertNotIn("/api/", content)

    def test_home_page_uses_fixed_canonical_and_og_url(self):
        response = self.client.get(reverse("home"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<link rel="canonical" href="https://eduitit.site/">', content)
        self.assertIn('<meta property="og:url" content="https://eduitit.site/">', content)
        self.assertIn('<meta property="og:title" content="에듀잇티 - 선생님의 스마트한 하루">', content)
        self.assertIn("<title>에듀잇티 - 선생님의 스마트한 하루</title>", content)
        self.assertIn('<link rel="icon" href="/favicon.ico" sizes="any">', content)
        self.assertIn("eduitit_og.png", content)
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
            ("product_list", "교사용 서비스 카탈로그 | Eduitit", "https://eduitit.site/products/", "수업 준비, 학급 운영, 문서 작성, 활동 도구를 상황별로 정리한 에듀잇티 서비스 카탈로그입니다."),
            ("portfolio:list", "AI 연수·협업 포트폴리오 | Eduitit", "https://eduitit.site/portfolio/", "AI 활용 연수, 에듀테크 설계, 교실 적용 사례와 협업 제안을 한 곳에서 확인하는 포트폴리오입니다."),
            ("insights:list", "교실 AI 인사이트 | Eduitit", "https://eduitit.site/insights/", "수업, 학급 운영, AI 활용에 도움이 되는 실전 인사이트를 교사 관점으로 정리했습니다."),
            ("about", "에듀잇티 소개 | 교사의 스마트한 하루", "https://eduitit.site/about/", "교사의 시간을 아껴 주는 도구를 왜, 어떻게 만들고 있는지 에듀잇티의 방향과 철학을 소개합니다."),
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
            ("account_login", "로그인 | Eduitit", "https://eduitit.site/accounts/login/", "에듀잇티에 로그인하고 교실 운영 도구를 이어서 사용하세요."),
            ("account_signup", "회원가입 | Eduitit", "https://eduitit.site/accounts/signup/", "에듀잇티 계정으로 교실 운영 도구를 바로 시작하세요."),
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
                self.assertIn("eduitit_og.png", content)
                self.assertIn(html.escape(description), content)
                self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_ocrdesk_page_uses_explicit_noindex_meta(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("ocrdesk:main"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>사진 글자 읽기 - Eduitit</title>", content)
        self.assertIn('<meta name="robots" content="noindex,nofollow">', content)
        self.assertIn(f'<link rel="canonical" href="https://eduitit.site{reverse("ocrdesk:main")}">', content)
        self.assertIn('<meta property="og:title" content="사진 글자 읽기 - Eduitit">', content)
        self.assertIn('<meta name="twitter:title" content="사진 글자 읽기 - Eduitit">', content)
        self.assertIn(
            '<meta property="og:description" content="사진을 놓거나 고르면 미리보기를 보여주고 바로 읽기를 시작합니다.',
            content,
        )
        self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_schoolcomm_main_uses_noindex_meta(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("schoolcomm:main"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>끼리끼리 채팅방 | Eduitit</title>", content)
        self.assertIn('<meta name="robots" content="noindex,nofollow">', content)
        self.assertIn(f'<link rel="canonical" href="https://eduitit.site{reverse("schoolcomm:main")}">', content)
        self.assertIn("동학년 선생님과 공지, 자료, 대화, 끼리끼리 캘린더를 한 화면에서 정리하는 교사용 채팅방입니다.", content)
        self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_tts_announce_page_gets_explicit_meta(self):
        response = self.client.get(reverse("tts_announce"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>교실 방송 TTS - Eduitit</title>", content)
        self.assertIn(f'<link rel="canonical" href="https://eduitit.site{reverse("tts_announce")}">', content)
        self.assertIn('<meta property="og:title" content="교실 방송 TTS - Eduitit">', content)
        self.assertIn("학생들에게 안내, 집중 신호, 정리 멘트를 바로 읽어 줘야 하는 교사에게 맞는 도구입니다.", content)
        self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_handoff_landing_uses_explicit_meta(self):
        response = self.client.get(reverse("handoff:landing"))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>배부 체크 - Eduitit</title>", content)
        self.assertIn('<link rel="canonical" href="https://eduitit.site/handoff/">', content)
        self.assertIn('<meta property="og:title" content="배부 체크 - Eduitit">', content)
        self.assertIn('<meta name="twitter:title" content="배부 체크 - Eduitit">', content)
        self.assertIn(
            '<meta name="description" content="명단을 저장해 두고 배부할 때 수령 여부만 빠르게 체크하는 교사용 배부 기록 도구입니다.">',
            content,
        )
        self.assertIn('"@type":"CollectionPage"', content)
        self.assertIn('"@type":"BreadcrumbList"', content)
        self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_schoolprograms_landing_uses_public_service_meta_and_schema(self):
        response = self.client.get(reverse("schoolprograms:landing"))
        content = response.content.decode("utf-8")
        canonical = f"https://eduitit.site{reverse('schoolprograms:landing')}"

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>학교 체험·행사 찾기 | Eduitit</title>", content)
        self.assertIn(f'<link rel="canonical" href="{canonical}">', content)
        self.assertIn(f'<meta property="og:url" content="{canonical}">', content)
        self.assertIn("지역과 주제로 학교로 찾아오는 체험학습, 교사연수, 학교행사를 바로 비교하고 문의하세요.", content)
        self.assertIn('"@type":"CollectionPage"', content)
        self.assertIn('"@type":"BreadcrumbList"', content)
        self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_schoolprograms_filtered_landing_uses_canonical_root_and_noindex(self):
        response = self.client.get(
            reverse("schoolprograms:landing"),
            {"category": ProgramListing.Category.FIELDTRIP},
        )
        content = response.content.decode("utf-8")
        canonical = f"https://eduitit.site{reverse('schoolprograms:landing')}"

        self.assertEqual(response.status_code, 200)
        self.assertIn(f'<link rel="canonical" href="{canonical}">', content)
        self.assertIn('<meta name="robots" content="noindex,follow">', content)
        self.assertEqual(response["X-Robots-Tag"], "noindex, follow")

    def test_schoolprograms_listing_detail_uses_article_meta_and_schema(self):
        response = self.client.get(reverse("schoolprograms:listing_detail", args=[self.schoolprogram_listing.slug]))
        content = response.content.decode("utf-8")
        canonical = f"https://eduitit.site{reverse('schoolprograms:listing_detail', args=[self.schoolprogram_listing.slug])}"

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"<title>{html.escape(self.schoolprogram_listing.title)} | 학교 체험·행사 찾기</title>", content)
        self.assertIn(f'<link rel="canonical" href="{canonical}">', content)
        self.assertIn(f'<meta property="og:url" content="{canonical}">', content)
        self.assertIn('<meta property="og:type" content="article">', content)
        self.assertIn('"@type":"Article"', content)
        self.assertIn('"@type":"BreadcrumbList"', content)
        self.assertIn(self.schoolprogram_provider.provider_name, content)
        self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_schoolprograms_provider_detail_uses_collection_meta_and_schema(self):
        response = self.client.get(reverse("schoolprograms:provider_detail", args=[self.schoolprogram_provider.slug]))
        content = response.content.decode("utf-8")
        canonical = f"https://eduitit.site{reverse('schoolprograms:provider_detail', args=[self.schoolprogram_provider.slug])}"

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"<title>{html.escape(self.schoolprogram_provider.provider_name)} | 학교 체험·행사 찾기</title>", content)
        self.assertIn(f'<link rel="canonical" href="{canonical}">', content)
        self.assertIn(f'<meta property="og:url" content="{canonical}">', content)
        self.assertIn('"@type":"CollectionPage"', content)
        self.assertIn('"@type":"Organization"', content)
        self.assertIn('"@type":"BreadcrumbList"', content)
        self.assertIn(self.schoolprogram_provider.contact_email, content)
        self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_collect_and_handoff_landing_pages_get_explicit_meta(self):
        cases = (
            (
                reverse("collect:landing"),
                "가뿐 수합 - Eduitit",
                "https://eduitit.site/collect/",
                "QR 또는 입장코드로 파일, 링크, 텍스트, 선택형 응답을 빠르게 모으는 교사용 수합 도구입니다.",
            ),
            (
                reverse("handoff:landing"),
                "배부 체크 - Eduitit",
                "https://eduitit.site/handoff/",
                "명단을 저장해 두고 배부할 때 수령 여부만 빠르게 체크하는 교사용 배부 기록 도구입니다.",
            ),
        )

        for path, title, canonical, description in cases:
            with self.subTest(path=path):
                response = self.client.get(path)
                content = response.content.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"<title>{html.escape(title)}</title>", content)
                self.assertIn(f'<link rel="canonical" href="{canonical}">', content)
                self.assertIn(f'<meta property="og:url" content="{canonical}">', content)
                self.assertIn(html.escape(description), content)
                self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_collect_submit_page_is_noindex_with_request_specific_meta(self):
        response = self.client.get(reverse("collect:submit", kwargs={"request_id": self.collect_request.id}))
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>과학 실험 보고서 - 제출하기</title>", content)
        self.assertIn('<meta name="robots" content="noindex,nofollow">', content)
        self.assertIn(
            f'<link rel="canonical" href="https://eduitit.site{reverse("collect:submit", kwargs={"request_id": self.collect_request.id})}">',
            content,
        )
        self.assertIn("실험 사진과 관찰 기록을 제출해 주세요.", content)
        self.assertNotIn(DEFAULT_HOME_DESCRIPTION, content)

    def test_game_pages_use_explicit_canonical_meta(self):
        chess_response = self.client.get(f"{reverse('chess:play')}?mode=ai&difficulty=hard")
        chess_content = chess_response.content.decode("utf-8")

        self.assertEqual(chess_response.status_code, 200)
        self.assertIn('<link rel="canonical" href="https://eduitit.site/chess/play/">', chess_content)
        self.assertIn("로컬 대전 또는 AI 대전으로 체스를 바로 플레이할 수 있는 게임 화면입니다.", chess_content)
        self.assertNotIn(DEFAULT_HOME_DESCRIPTION, chess_content)

        fairy_response = self.client.get(reverse("fairy_games:play", kwargs={"variant": "dobutsu"}))
        fairy_content = fairy_response.content.decode("utf-8")

        self.assertEqual(fairy_response.status_code, 200)
        self.assertIn("<title>동물 장기 플레이 - Eduitit</title>", fairy_content)
        self.assertIn('<link rel="canonical" href="https://eduitit.site/fairy-games/dobutsu/play/">', fairy_content)
        self.assertIn("3x4 작은 판에서 사자를 지키는 전략 게임 지금 바로 동물 장기를 플레이해 보세요.", fairy_content)
        self.assertNotIn(DEFAULT_HOME_DESCRIPTION, fairy_content)

    def test_public_pages_expose_semantic_landmarks(self):
        cases = (
            (reverse("collect:landing"), ("<main", "<header", "<article", "<nav")),
            (reverse("handoff:landing"), ("<main", "<header", "<article", "<nav")),
            (reverse("chess:index"), ("<main", "<header", "<article", "<nav")),
            (reverse("chess:play"), ("<main", "<header", "<section", "<aside")),
            (reverse("fairy_games:rules", kwargs={"variant": "dobutsu"}), ("<main", "<article", "<nav")),
        )

        for path, markers in cases:
            with self.subTest(path=path):
                response = self.client.get(path)
                content = response.content.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                for marker in markers:
                    self.assertIn(marker, content)

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

    def test_route_canonical_products_use_noindex_headers_on_detail_pages(self):
        cases = (
            self.handoff_service,
            self.noticegen_service,
            self.schoolprograms_service,
        )

        for product in cases:
            with self.subTest(product=product.launch_route_name):
                response = self.client.get(reverse("product_detail", kwargs={"pk": product.pk}))
                content = response.content.decode("utf-8")
                self.assertEqual(response.status_code, 200)
                self.assertIn('<meta name="robots" content="noindex,nofollow">', content)
                self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
