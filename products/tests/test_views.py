from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from core.guide_links import SERVICE_GUIDE_PADLET_URL
from core.models import UserProfile
from products.models import DTSettings, ManualSection, Product, ProductFeature, ServiceManual


@override_settings(HOME_V2_ENABLED=False)
class ProductViewTests(TestCase):
    """Test suite for product views following TDD approach"""
    
    def setUp(self):
        """Create test products"""
        self.client = Client()
        
        # Create featured product
        self.featured_product = Product.objects.create(
            title="Featured Tool",
            description="This is featured",
            price=0,
            is_active=True,
            is_featured=True
        )
        
        # Create active but not featured products
        self.active_product1 = Product.objects.create(
            title="Active Tool 1",
            description="This is active but not featured",
            price=0,
            is_active=True,
            is_featured=False
        )
        
        self.active_product2 = Product.objects.create(
            title="Active Tool 2",
            description="Another active tool",
            price=0,
            is_active=True,
            is_featured=False
        )
        
        # Create inactive product
        self.inactive_product = Product.objects.create(
            title="Inactive Tool",
            description="This should not appear",
            price=0,
            is_active=False,
            is_featured=False
        )
    
    def test_all_active_products_display_on_homepage(self):
        """All active products should appear on homepage regardless of featured status"""
        response = self.client.get(reverse('home'))
        
        # Check that all active products are in context
        products = response.context['products']
        
        # Count active products in database
        active_count = Product.objects.filter(is_active=True).count()
        self.assertEqual(len(products), active_count)
        
        # Verify our test products are included
        product_titles = [p.title for p in products]
        self.assertIn("Featured Tool", product_titles)
        self.assertIn("Active Tool 1", product_titles)
        self.assertIn("Active Tool 2", product_titles)
        
        # Verify inactive product is NOT included
        self.assertNotIn("Inactive Tool", product_titles)
    
    def test_featured_product_appears_in_hero_card(self):
        """Featured product should be available in context for hero card"""
        response = self.client.get(reverse('home'))
        
        # Check featured_product exists in context
        self.assertIn('featured_product', response.context)
        
        # Verify it's the correct product
        featured = response.context['featured_product']
        self.assertEqual(featured.title, "Featured Tool")
        self.assertTrue(featured.is_featured)
    
    def test_product_detail_page_returns_200(self):
        """Product detail page should return 200 for valid product"""
        response = self.client.get(
            reverse('product_detail', kwargs={'pk': self.active_product1.pk})
        )
        self.assertEqual(response.status_code, 200)
    
    def test_product_detail_page_shows_correct_product(self):
        """Product detail page should display correct product information"""
        response = self.client.get(
            reverse('product_detail', kwargs={'pk': self.active_product1.pk})
        )
        
        # Check product is in context
        self.assertEqual(response.context['product'].title, "Active Tool 1")
        
        # Check title appears in rendered HTML
        self.assertContains(response, "Active Tool 1")


class ProductDetailHeroTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_product_detail_shows_value_prop_access_and_manual_cta(self):
        product = Product.objects.create(
            title="알림장 도우미",
            lead_text="대상과 주제를 고르면 바로 보낼 문구를 빠르게 만듭니다.",
            description="알림장과 가정 안내 문구를 짧은 시간 안에 정리할 수 있습니다.",
            solve_text="알림장 문구를 빠르게 정리하고 싶어요",
            result_text="복사할 수 있는 안내 문구",
            time_text="1분",
            price=0,
            is_active=True,
            is_guest_allowed=False,
            service_type="work",
            launch_route_name="noticegen:main",
        )
        manual = ServiceManual.objects.create(
            product=product,
            title="알림장 도우미 사용 가이드",
            description="대상 선택부터 복사까지 빠르게 안내합니다.",
            is_published=True,
        )
        ManualSection.objects.create(
            manual=manual,
            title="대상 고르기",
            content="저학년, 고학년, 학부모 중 대상을 먼저 선택합니다.",
            display_order=1,
        )
        ManualSection.objects.create(
            manual=manual,
            title="문구 만들기",
            content="주제와 전달사항을 적고 생성 버튼을 누릅니다.",
            display_order=2,
        )
        ProductFeature.objects.create(
            product=product,
            icon="🎯",
            title="대상별 문구 분기",
            description="대상에 맞는 톤으로 안내 문구를 바로 정리합니다.",
        )

        response = self.client.get(reverse("product_detail", kwargs={"pk": product.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "한 줄 가치 제안")
        self.assertContains(response, "누구를 위한가")
        self.assertContains(response, "로그인 필요 여부")
        self.assertContains(response, "1분 데모/스크린샷")
        self.assertContains(response, "대상 고르기")
        self.assertContains(response, "문구 만들기")
        self.assertContains(response, SERVICE_GUIDE_PADLET_URL)
        self.assertContains(response, reverse("account_login"))
        self.assertEqual(response.context["guide_href"], SERVICE_GUIDE_PADLET_URL)
        self.assertEqual(response.context["product_access_label"], "로그인 필요")
        self.assertEqual(response.context["start_label"], "로그인하고 시작")

    def test_product_detail_falls_back_to_guide_list_and_public_preview(self):
        product = Product.objects.create(
            title="공개 체험 도구",
            lead_text="로그인 없이도 핵심 흐름을 먼저 볼 수 있습니다.",
            description="외부 링크로 바로 이어지는 공개 체험형 서비스입니다.",
            solve_text="바로 체험해보고 싶어요",
            price=0,
            is_active=True,
            is_guest_allowed=True,
            service_type="etc",
            external_url="https://example.com/start",
        )

        response = self.client.get(reverse("product_detail", kwargs={"pk": product.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "공개 체험")
        self.assertContains(response, "가이드 찾기")
        self.assertContains(response, SERVICE_GUIDE_PADLET_URL)
        self.assertContains(response, "https://example.com/start")
        self.assertEqual(response.context["guide_href"], SERVICE_GUIDE_PADLET_URL)
        self.assertEqual(response.context["product_demo_block"]["kind"], "steps")
        self.assertGreaterEqual(len(response.context["quick_preview_steps"]), 1)

    def test_product_detail_marks_login_only_route_as_login_required_even_when_guest_flag_is_on(self):
        product = Product.objects.create(
            title="인포보드",
            lead_text="자료를 모으고 정리합니다.",
            description="교사용 대시보드에서 보드를 관리합니다.",
            solve_text="교실 자료를 모아 관리하고 싶어요",
            price=0,
            is_active=True,
            is_guest_allowed=True,
            service_type="work",
            launch_route_name="infoboard:dashboard",
        )

        response = self.client.get(reverse("product_detail", kwargs={"pk": product.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["product_access_label"], "로그인 필요")
        self.assertEqual(response.context["launch_href"], reverse("infoboard:dashboard"))
        self.assertEqual(
            response.context["start_href"],
            f"{reverse('account_login')}?{urlencode({'next': reverse('infoboard:dashboard')})}",
        )
        self.assertEqual(response.context["start_label"], "로그인하고 시작")

    def test_product_detail_uses_public_happy_seed_landing_for_guest_and_dashboard_for_teacher(self):
        product = Product.objects.create(
            title="행복의 씨앗",
            lead_text="학급 루틴을 차근차근 키웁니다.",
            description="긍정 행동 기록과 보상 흐름을 운영합니다.",
            solve_text="공개 소개부터 보고 싶어요",
            price=0,
            is_active=True,
            is_guest_allowed=True,
            service_type="classroom",
            launch_route_name="happy_seed:dashboard",
        )

        guest_response = self.client.get(reverse("product_detail", kwargs={"pk": product.pk}))

        self.assertEqual(guest_response.status_code, 200)
        self.assertEqual(guest_response.context["product_access_label"], "미리보기 가능")
        self.assertEqual(guest_response.context["launch_href"], reverse("happy_seed:landing"))
        self.assertEqual(guest_response.context["start_href"], reverse("happy_seed:landing"))
        self.assertEqual(guest_response.context["start_label"], "바로 체험하기")

        teacher = get_user_model().objects.create_user(
            username="happy-seed-teacher",
            email="happy-seed-teacher@example.com",
            password="pw-12345",
        )
        teacher_profile, _ = UserProfile.objects.get_or_create(user=teacher)
        teacher_profile.nickname = "행복교사"
        teacher_profile.role = "school"
        teacher_profile.save(update_fields=["nickname", "role"])
        self.client.force_login(teacher)
        teacher_response = self.client.get(reverse("product_detail", kwargs={"pk": product.pk}))

        self.assertEqual(teacher_response.status_code, 200)
        self.assertEqual(teacher_response.context["launch_href"], reverse("happy_seed:dashboard"))
        self.assertEqual(teacher_response.context["start_href"], reverse("happy_seed:dashboard"))


class SheetbookDiscoveryVisibilityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.sheetbook_product = Product.objects.create(
            title="교무수첩",
            description="표 작업",
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='sheetbook:index',
        )
        self.calendar_product = Product.objects.create(
            title="학급 캘린더",
            description="일정 관리",
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='classcalendar:main',
        )
        self.today_ops_product = Product.objects.create(
            title="운영 도구",
            description="오늘 운영 흐름",
            price=0,
            is_active=True,
            service_type='classroom',
        )
        self.prep_product = Product.objects.create(
            title="문서 작성 도구",
            description="문서 작성",
            price=0,
            is_active=True,
            service_type='work',
        )
        self.calendar_manual = ServiceManual.objects.create(
            product=self.calendar_product,
            title="학급 캘린더 시작하기",
            description="일정 흐름 안내",
            is_published=True,
        )
        self.visible_manual = ServiceManual.objects.create(
            product=self.prep_product,
            title="문서 작성 도구 시작하기",
            description="문서 작성 흐름 안내",
            is_published=True,
        )

    @override_settings(SHEETBOOK_ENABLED=True, SHEETBOOK_DISCOVERY_VISIBLE=True)
    def test_catalog_shows_active_sheetbook_and_calendar_products(self):
        response = self.client.get(reverse('product_list'))

        product_titles = [product.title for product in response.context['products']]
        expected_count = Product.objects.filter(is_active=True).count()

        self.assertEqual(response.status_code, 200)
        self.assertIn('교무수첩', product_titles)
        self.assertIn('학급 캘린더', product_titles)
        self.assertIn('운영 도구', product_titles)
        self.assertContains(response, '학급 기록 보드')
        self.assertEqual(response.context['total_count'], expected_count)
        self.assertEqual(response.context['catalog_hub']['title'], '메인 캘린더는 홈에서 시작합니다')

    def test_catalog_hides_sheetbook_when_runtime_disabled(self):
        response = self.client.get(reverse('product_list'))

        product_titles = [product.title for product in response.context['products']]

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('교무수첩', product_titles)
        self.assertIn('학급 캘린더', product_titles)
        self.assertNotContains(response, '학급 기록 보드')

    def test_catalog_hides_sheetbook_and_calendar_when_inactive(self):
        self.sheetbook_product.is_active = False
        self.sheetbook_product.save(update_fields=['is_active'])
        self.calendar_product.is_active = False
        self.calendar_product.save(update_fields=['is_active'])

        response = self.client.get(reverse('product_list'))

        product_titles = [product.title for product in response.context['products']]
        expected_count = Product.objects.filter(is_active=True).count()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('교무수첩', product_titles)
        self.assertNotIn('학급 캘린더', product_titles)
        self.assertIn('운영 도구', product_titles)
        self.assertNotContains(response, '교무수첩')
        self.assertEqual(response.context['total_count'], expected_count)

    def test_catalog_cards_use_start_copy_and_public_meta_contract(self):
        response = self.client.get(reverse('product_list'))
        content = ''.join(response.content.decode('utf-8').split())
        visible_product = next(product for product in response.context['products'] if product.id == self.prep_product.id)
        card_cta_prefix = 'inline-flexitems-centergap-1.5rounded-xlbg-slate-900px-3py-2text-smfont-boldtext-whitetransitiongroup-hover:bg-indigo-600">'

        self.assertIn('로그인필요', content)
        self.assertIn('시작하기', content)
        self.assertIn(f'{card_cta_prefix}시작하기', content)
        self.assertNotIn(f'{card_cta_prefix}열기', content)
        self.assertEqual(visible_product.guide_url, SERVICE_GUIDE_PADLET_URL)
        self.assertEqual(response.context['catalog_hub']['guide_url'], SERVICE_GUIDE_PADLET_URL)
        self.assertContains(response, SERVICE_GUIDE_PADLET_URL)

    def test_catalog_uses_hwpxchat_task_and_support_copy(self):
        hwpx_product = Product.objects.create(
            title="한글문서 AI야 읽어줘",
            lead_text="공문이나 한글 문서를 올리면 해야 할 일, 기한, 전달 대상을 카드로 정리해 드려요.",
            description="공문을 읽어 실행용 업무 카드로 정리합니다.",
            solve_text="공문에서 해야 할 일을 바로 정리해요",
            result_text="실행용 업무 카드",
            price=0,
            is_active=True,
            service_type='work',
            launch_route_name='hwpxchat:main',
        )
        ServiceManual.objects.create(
            product=hwpx_product,
            title="한글문서 AI야 읽어줘 사용 가이드",
            description="공문 정리 시작 가이드",
            is_published=True,
        )

        response = self.client.get(reverse('product_list'))

        visible_product = next(product for product in response.context['products'] if product.id == hwpx_product.id)
        self.assertEqual(visible_product.teacher_first_task_label, '공문에서 해야 할 일을 바로 정리해요')
        self.assertEqual(
            visible_product.teacher_first_support_label,
            '공문이나 한글 문서를 올리면 해야 할 일, 기한, 전달 대상을 카드로 정리해 드려요.',
        )
        self.assertContains(response, '한글문서 AI야 읽어줘')
        self.assertContains(response, '공문에서 해야 할 일을 바로 정리해요')
        self.assertContains(response, '공문이나 한글 문서를 올리면 해야 할 일, 기한, 전달 대상을 카드로 정리해 드려요.')

    def test_catalog_section_filter_shows_selected_scenario_only(self):
        response = self.client.get(f"{reverse('product_list')}?section=today_ops")
        section_titles = [section['title'] for section in response.context['scenario_sections']]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(section_titles, ['오늘 운영'])
        self.assertEqual(len(response.context['scenario_sections']), 1)
        self.assertEqual(response.context['selected_scenario_section']['key'], 'today_ops')
        self.assertContains(response, '선택된 보기 오늘 운영')

    def test_catalog_invalid_section_filter_falls_back_to_full_catalog(self):
        response = self.client.get(f"{reverse('product_list')}?section=unknown")
        section_titles = [section['title'] for section in response.context['scenario_sections']]

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['selected_scenario_section'])
        self.assertIn('오늘 운영', section_titles)
        self.assertIn('수업 준비', section_titles)


class ProductDevicePolicyTests(TestCase):
    """Device policy tests for large-screen-only product pages."""

    def setUp(self):
        self.client = Client()
        self.iphone_ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        )
        self.ipad_ua = (
            "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        )

    def test_yut_blocks_iphone_user_agent(self):
        response = self.client.get(
            reverse('yut_game'),
            HTTP_USER_AGENT=self.iphone_ua,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/mobile_not_supported.html')
        self.assertContains(response, "force_desktop=1")

    def test_yut_allows_ipad_user_agent(self):
        response = self.client.get(
            reverse('yut_game'),
            HTTP_USER_AGENT=self.ipad_ua,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/yut_game.html')

    def test_dutyticker_allows_ipad_user_agent(self):
        response = self.client.get(
            reverse('dutyticker'),
            HTTP_USER_AGENT=self.ipad_ua,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/dutyticker/main.html')

    def test_dutyticker_blocks_iphone_user_agent(self):
        response = self.client.get(
            reverse('dutyticker'),
            HTTP_USER_AGENT=self.iphone_ua,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/mobile_not_supported.html')

    def test_mobile_block_template_uses_short_teacher_first_actions(self):
        response = self.client.get(
            reverse('yut_game'),
            HTTP_USER_AGENT=self.iphone_ua,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '그래도 열기')
        self.assertContains(response, '홈으로')
        self.assertNotContains(response, '그래도 계속 진행')

    def test_yut_force_desktop_bypasses_phone_block(self):
        response = self.client.get(
            f"{reverse('yut_game')}?force_desktop=1",
            HTTP_USER_AGENT=self.iphone_ua,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/yut_game.html')

    def test_dutyticker_force_desktop_bypasses_phone_block(self):
        response = self.client.get(
            f"{reverse('dutyticker')}?force_desktop=1",
            HTTP_USER_AGENT=self.iphone_ua,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/dutyticker/main.html')

    @override_settings(ALLOW_TABLET_ACCESS=False)
    def test_yut_blocks_ipad_when_tablet_access_disabled(self):
        response = self.client.get(
            reverse('yut_game'),
            HTTP_USER_AGENT=self.ipad_ua,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/mobile_not_supported.html')

class DutyTickerThemeBootstrapTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username='dt-theme', password='pw123456', email='dt-theme@example.com')
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = '담임교사'
        profile.save(update_fields=['nickname'])

    def test_dutyticker_view_bootstraps_saved_theme_before_app_init(self):
        self.client.force_login(self.user)
        DTSettings.objects.create(user=self.user, theme='sunny')

        response = self.client.get(reverse('dutyticker'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'window.__DT_INITIAL_THEME__ = "sunny";')
        self.assertContains(response, "document.documentElement.setAttribute('data-theme', window.__DT_INITIAL_THEME__);")
