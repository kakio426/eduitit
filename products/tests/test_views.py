from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from core.models import UserProfile
from products.models import DTSettings, Product, ServiceManual


def _create_onboarded_user(username, *, password='password', email=None):
    user = get_user_model().objects.create_user(
        username=username,
        password=password,
        email=email or f'{username}@example.com',
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = username
    profile.role = 'school'
    profile.save(update_fields=['nickname', 'role'])
    return user


@override_settings(HOME_V2_ENABLED=False, HOME_LAYOUT_VERSION='v1')
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
            is_featured=True,
            service_type='edutech',
            launch_route_name='tool_guide',
            display_order=-1000,
        )
        
        # Create active but not featured products
        self.active_product1 = Product.objects.create(
            title="Active Tool 1",
            description="This is active but not featured",
            price=0,
            is_active=True,
            is_featured=False,
            service_type='edutech',
            launch_route_name='insights:list',
        )
        
        self.active_product2 = Product.objects.create(
            title="Active Tool 2",
            description="Another active tool",
            price=0,
            is_active=True,
            is_featured=False,
            service_type='game',
            launch_route_name='yut_game',
        )
        
        # Create inactive product
        self.inactive_product = Product.objects.create(
            title="Inactive Tool",
            description="This should not appear",
            price=0,
            is_active=False,
            is_featured=False,
            service_type='counsel',
            launch_route_name='fortune:saju',
        )
    
    def test_all_active_products_display_on_homepage(self):
        """비로그인 홈에는 공개 후보 중 활성 서비스만 노출된다."""
        response = self.client.get(reverse('home'))

        products = response.context['products']
        product_titles = [p.title for p in products]
        self.assertIn("Featured Tool", product_titles)
        self.assertIn("Active Tool 1", product_titles)
        self.assertIn("Active Tool 2", product_titles)
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


class SheetbookDiscoveryVisibilityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = _create_onboarded_user("catalog-user")
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

    def test_catalog_shows_active_sheetbook_and_calendar_products(self):
        self.client.force_login(self.user)
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

    def test_catalog_hides_sheetbook_and_calendar_when_inactive(self):
        self.client.force_login(self.user)
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
        self.client.force_login(self.user)
        response = self.client.get(reverse('product_list'))
        content = ''.join(response.content.decode('utf-8').split())
        visible_product = next(product for product in response.context['products'] if product.id == self.prep_product.id)
        card_cta_prefix = 'inline-flexitems-centergap-1.5rounded-xlbg-slate-900px-3py-2text-smfont-boldtext-whitetransitiongroup-hover:bg-indigo-600">'

        self.assertIn('로그인필요', content)
        self.assertIn('시작하기', content)
        self.assertIn(f'{card_cta_prefix}시작하기', content)
        self.assertNotIn(f'{card_cta_prefix}열기', content)
        self.assertTrue(visible_product.guide_url.endswith(reverse('service_guide_detail', kwargs={'pk': self.visible_manual.pk})))

    def test_catalog_section_filter_shows_selected_scenario_only(self):
        self.client.force_login(self.user)
        response = self.client.get(f"{reverse('product_list')}?section=today_ops")
        section_titles = [section['title'] for section in response.context['scenario_sections']]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(section_titles, ['오늘 운영'])
        self.assertEqual(response.context['selected_scenario_section']['key'], 'today_ops')
        self.assertContains(response, '선택된 보기 오늘 운영')
        self.assertNotContains(response, '수업 준비')

    def test_catalog_invalid_section_filter_falls_back_to_full_catalog(self):
        self.client.force_login(self.user)
        response = self.client.get(f"{reverse('product_list')}?section=unknown")
        section_titles = [section['title'] for section in response.context['scenario_sections']]

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['selected_scenario_section'])
        self.assertIn('오늘 운영', section_titles)
        self.assertIn('수업 준비', section_titles)

    def test_guest_catalog_only_shows_public_candidates(self):
        public_product = Product.objects.create(
            title="쌤BTI",
            description="성향 분석",
            price=0,
            is_active=True,
            service_type='counsel',
            launch_route_name='ssambti:main',
        )

        response = self.client.get(reverse('product_list'))
        product_titles = [product.title for product in response.context['products']]

        self.assertEqual(response.status_code, 200)
        self.assertIn(public_product.title, product_titles)
        self.assertNotIn('교무수첩', product_titles)
        self.assertNotIn('학급 캘린더', product_titles)
        self.assertNotIn('운영 도구', product_titles)
        self.assertNotIn('문서 작성 도구', product_titles)


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
