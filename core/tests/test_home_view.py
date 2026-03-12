import json

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from core.teacher_first_cards import build_favorite_service_title
from core.mini_apps import (
    HOME_LAYOUT_EXCLUDED,
    HOME_LAYOUT_QUICK,
    HOME_LAYOUT_STARTER,
    HOME_OVERFLOW_PROMOTE,
    HOME_SURFACE_ACTION,
    HOME_SURFACE_CONTENT,
    plan_home_action_surface,
)
from products.models import Product
from core.models import Post, ProductFavorite, ProductUsageLog, UserProfile


def _create_onboarded_user(username, email=None, nickname=None):
    """온보딩 완료 상태의 테스트 유저 생성"""
    email = email or f'{username}@test.com'
    nickname = nickname or username
    user = User.objects.create_user(username, email, 'pass1234')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = nickname
    profile.role = 'school'
    profile.save()
    return user


def _create_posts(count=4, *, username='snsauthor'):
    author = _create_onboarded_user(username)
    created_posts = []
    for index in range(count):
        created_posts.append(
            Post.objects.create(
                author=author,
                content=f'소통 글 {index + 1}',
            )
        )
    return created_posts


@override_settings(HOME_V2_ENABLED=False)
class HomeViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(
            title="테스트 서비스", description="설명", price=0,
            is_active=True, service_type='classroom',
        )

    def _create_sheetbook_product(self, title='숨김 교무수첩'):
        return Product.objects.create(
            title=title,
            description='표 작업',
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='sheetbook:index',
        )

    def test_home_anonymous_200(self):
        """비로그인 홈 200 응답"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_home_anonymous_contains_product(self):
        """비로그인 홈에 서비스 카드가 표시됨"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('테스트 서비스', content)
        self.assertIn(f'data-product-id="{self.product.id}"', content)

    def test_home_nav_contains_single_help_hub_link(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('이용 안내', content)
        self.assertIn('https://padlet.com/kakio1q2w/eduitit-wrjbzmk8oufxdzcv', content)

    def test_home_authenticated_200(self):
        """로그인 홈 200 응답"""
        _create_onboarded_user('testuser')
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_v1_service_launcher_json_in_context(self):
        """V1 홈에서도 글로벌 런처 컨텍스트를 제공"""
        response = self.client.get(reverse('home'))
        self.assertIn('service_launcher_json', response.context)

    @override_settings(SHEETBOOK_DISCOVERY_VISIBLE=False)
    def test_v1_home_hides_sheetbook_product_when_discovery_disabled(self):
        self._create_sheetbook_product()

        response = self.client.get(reverse('home'))
        product_titles = [product.title for product in response.context['products']]

        self.assertNotIn('숨김 교무수첩', product_titles)
        self.assertNotContains(response, '숨김 교무수첩')

    @override_settings(SHEETBOOK_DISCOVERY_VISIBLE=False)
    def test_v1_service_launcher_json_hides_sheetbook_when_discovery_disabled(self):
        self._create_sheetbook_product()

        response = self.client.get(reverse('home'))
        payload = json.loads(response.context['service_launcher_json'])
        titles = [item['title'] for item in payload]

        self.assertNotIn('숨김 교무수첩', titles)

    @override_settings(GLOBAL_SEARCH_ENABLED=False)
    def test_service_launcher_json_absent_when_global_search_disabled(self):
        """글로벌 검색 비활성화 시 컨텍스트에서 런처 데이터 제외"""
        response = self.client.get(reverse('home'))
        self.assertNotIn('service_launcher_json', response.context)

    def test_v1_mobile_sns_more_uses_toggle_not_anchor(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('@click="snsOpen = true"', content)
        self.assertNotIn('hx-select="#mobile-post-list-container"', content)
        self.assertNotIn('href="#sns-full-section"', content)

    def test_v1_authenticated_mobile_sns_more_uses_toggle_not_anchor(self):
        _create_onboarded_user('v1authuser')
        self.client.login(username='v1authuser', password='pass1234')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('@click="snsOpen = true"', content)
        self.assertNotIn('hx-select="#mobile-post-list-container"', content)
        self.assertNotIn('href="#sns-full-section-auth"', content)


@override_settings(HOME_V2_ENABLED=True)
class HomeV2ViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.p1 = Product.objects.create(
            title="수업 도구", description="수업용", price=0,
            is_active=True, service_type='classroom', is_featured=True,
            solve_text='수업을 준비해요',
        )
        self.p2 = Product.objects.create(
            title="행정 도구", description="행정용", price=0,
            is_active=True, service_type='work',
        )
        self.p3 = Product.objects.create(
            title="테스트 게임", description="게임", price=0,
            is_active=True, service_type='game',
        )

    def _login(self, username='v2user', nickname=None):
        user = _create_onboarded_user(username, nickname=nickname)
        self.client.login(username=username, password='pass1234')
        return user

    def _create_sheetbook_product(self, title='숨김 교무수첩'):
        return Product.objects.create(
            title=title,
            description='표 작업',
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='sheetbook:index',
        )

    def test_v2_anonymous_200(self):
        """V2 비로그인 홈 200 응답"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_v2_anonymous_has_sections(self):
        """V2 비로그인 홈에 목적별 섹션 존재"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('수합·서명', content)
        self.assertIn('문서·작성', content)

    def test_v2_anonymous_has_login_cta(self):
        """V2 비로그인 홈에 로그인 CTA 존재"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('로그인하고 시작하기', content)

    def test_v2_anonymous_keeps_guest_home_without_mini_app_rail(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertNotIn('data-home-v2-mini-app-rail="true"', content)
        self.assertNotIn('data-home-mini-app-shell="true"', content)

    def test_v2_anonymous_moves_sns_preview_above_services_and_login_cta(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        sns_index = content.index('sns-full-section-v2')
        services_index = content.index('data-home-v2-service-groups="true"')
        login_index = content.index('로그인하고 시작하기')

        self.assertLess(sns_index, services_index)
        self.assertLess(sns_index, login_index)

    def test_v2_anonymous_has_game_banner(self):
        """V2 비로그인 홈에 게임 배너 존재"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('테스트 게임', content)
        self.assertNotIn('학생용 QR', content)

    def test_v2_authenticated_has_student_games_qr_button(self):
        """V2 로그인 홈에 학생 게임 QR 버튼 존재"""
        self._login('gameqruser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('학생용 QR', content)
        self.assertIn('homeStudentGamesQrModal', content)

    def test_v2_anonymous_does_not_render_show_all_toggle(self):
        """V2 비로그인 홈에 전체 서비스 보기 토글이 노출되지 않음"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertNotIn('data-track="show_all_toggle"', content)
        self.assertNotIn('전체 서비스 보기', content)

    def test_v2_authenticated_200(self):
        """V2 로그인 홈 200 응답"""
        self._login('authuser')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_v2_authenticated_uses_compact_top_row_without_large_greeting(self):
        """V2 로그인 홈은 큰 인사말 대신 압축된 상단 행을 사용"""
        self._login('greetuser', nickname='홍길동')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertNotIn('선생님, 안녕하세요', content)
        self.assertIn('data-global-service-launcher-trigger="true"', content)
        self.assertNotIn('서비스 검색...', content)

    def test_v2_authenticated_uses_stacked_top_zone_and_real_calendar(self):
        """V2 로그인 홈은 가운데 적층 + 오른쪽 월간 캘린더를 사용"""
        self._login('qauser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        today_index = content.index('data-home-v2-top-today="true"')
        favorites_index = content.index('data-home-v2-top-favorites="true"')
        calendar_index = content.index('data-home-v2-top-calendar="true"')

        self.assertLess(today_index, favorites_index)
        self.assertIn('data-home-v2-top-zone="true"', content)
        self.assertIn('학급 캘린더', content)
        self.assertIn('home-calendar-day', content)
        self.assertIn('data-home-v2-calendar-agenda="true"', content)
        self.assertNotIn('dayEventsModalOpen', content)
        self.assertNotIn('개인 캘린더', content)

    @override_settings(
        FEATURE_MESSAGE_CAPTURE_ENABLED=True,
        FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USERNAMES='capturehome',
        FEATURE_MESSAGE_CAPTURE_ITEM_TYPES=True,
    )
    def test_v2_authenticated_calendar_hub_shows_single_message_entry(self):
        self._login('capturehome')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('home-calendar-message-limits-data', content)
        self.assertIn('home-calendar-message-urls-data', content)
        self.assertIn('openMessageHub($event, \'capture\', { resetCapture: true })', content)
        self.assertIn('fa-comment-dots', content)
        self.assertNotIn('openMessageCaptureModal($event)', content)

    def test_v2_authenticated_widens_content_shell_and_keeps_favorites_two_up(self):
        user = self._login('balanceuser')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn("core/css/home_authenticated_v2.css", content)
        self.assertIn('data-home-v2-top-favorites-grid="true"', content)
        self.assertIn('home-v2-content-shell', content)
        self.assertIn('home-v2-top-zone', content)
        self.assertNotIn('<style>', content)
        self.assertNotIn('function initHomeV2Interactions()', content)
        self.assertNotIn('function buildCalendarMessageHubState()', content)

    def test_v2_authenticated_has_sections(self):
        """V2 로그인 홈에 목적별 섹션 존재"""
        self._login('secuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('수합·서명', content)
        self.assertIn('문서·작성', content)

    def test_v2_authenticated_orders_tablet_summary_before_services_and_game(self):
        self._login('tabletorder')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        top_zone_index = content.index('data-home-v2-top-zone="true"')
        summary_index = content.index('data-home-v2-tablet-community-summary="true"')
        service_index = content.index('data-home-v2-service-groups="true"')
        game_index = content.index('data-home-v2-game-section="true"')

        self.assertLess(top_zone_index, summary_index)
        self.assertLess(summary_index, service_index)
        self.assertLess(service_index, game_index)

    def test_v2_authenticated_renders_mini_app_rail_below_top_zone_and_before_services(self):
        self._login('minirailuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        top_zone_index = content.index('data-home-v2-top-zone="true"')
        mini_rail_index = content.index('data-home-v2-mini-app-rail="true"')
        summary_index = content.index('data-home-v2-tablet-community-summary="true"')
        service_index = content.index('data-home-v2-service-groups="true"')

        self.assertLess(top_zone_index, mini_rail_index)
        self.assertLess(mini_rail_index, summary_index)
        self.assertLess(mini_rail_index, service_index)

    def test_v2_authenticated_mini_app_rail_renders_three_pilot_shells(self):
        self._login('miniappuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-surface="action"', content)
        self.assertIn('data-home-action-grid="true"', content)
        self.assertNotIn('home-mini-app-track-wrap', content)
        self.assertContains(response, 'data-home-mini-app-key="noticegen"', count=1, html=False)
        self.assertContains(response, 'data-home-mini-app-key="qrgen"', count=1, html=False)
        self.assertContains(response, 'data-home-mini-app-key="prompt_lab"', count=1, html=False)
        self.assertContains(response, 'data-home-action-card-variant="starter"', count=1, html=False)
        self.assertContains(response, 'data-home-action-card-variant="quick"', count=2, html=False)
        self.assertContains(response, 'data-mini-app-action="open_full"', count=3, html=False)
        self.assertContains(response, 'data-mini-app-action="run"', count=2, html=False)
        self.assertIn(reverse('noticegen:generate_mini'), content)
        self.assertIn('createQrgenSingleLinkMiniApp', content)
        self.assertIn('createHomePromptLabMiniApp', content)
        self.assertIn('home-action-card--starter', content)
        self.assertIn('home-action-card--quick', content)

    def test_v2_authenticated_does_not_render_show_all_toggle(self):
        """V2 로그인 홈에서도 전체 서비스 보기 토글 미노출"""
        self._login('authnotoggle')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertNotIn('data-track="show_all_toggle"', content)
        self.assertNotIn('전체 서비스 보기', content)

    def test_v2_mini_card_has_data_product_id(self):
        """V2 미니 카드에 data-product-id 속성 존재"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-home-v2-service-card="true"', content)
        self.assertIn(f'data-product-id="{self.p1.id}"', content)

    def test_v2_mini_card_shows_normalized_home_summary(self):
        """V2 미니 카드는 홈 전용 요약 한 줄 계약을 사용"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('수업을 준비해요', content)
        self.assertIn('data-home-v2-service-card-body="true"', content)
        self.assertIn('data-home-v2-service-card-header="true"', content)
        self.assertIn('전체 보기', content)

    def test_v2_authenticated_favorite_cards_show_compact_body(self):
        user = self._login('favoritebodyuser')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-v2-favorite-card-header="true"', content)
        self.assertIn('data-home-v2-favorite-card-title="true"', content)
        self.assertIn('수업을 준비해요', content)

    def test_v2_service_board_uses_balanced_two_column_shell(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('md:grid-cols-2', content)
        self.assertNotIn('data-home-v2-section-more-link="true"', content)
        self.assertNotIn('repeat(auto-fit, minmax(min(100%, 300px), 360px)); justify-content: start;', content)

    def test_v2_context_section_preview_limit_is_two_for_all_sections(self):
        response = self.client.get(reverse('home'))
        for section in response.context.get('sections', []):
            self.assertLessEqual(len(section.get('products', [])), 2)
        for section in response.context.get('aux_sections', []):
            self.assertLessEqual(len(section.get('products', [])), 2)

    def test_v2_display_groups_pair_class_ops_with_refresh(self):
        Product.objects.create(
            title="상담 도구",
            description="상담용",
            price=0,
            is_active=True,
            service_type='counsel',
        )

        response = self.client.get(reverse('home'))

        primary_keys = [section['key'] for section in response.context.get('primary_display_sections', [])]
        secondary_keys = [section['key'] for section in response.context.get('secondary_display_sections', [])]

        self.assertEqual(primary_keys[:4], ['collect_sign', 'doc_write', 'class_ops', 'refresh'])
        self.assertNotIn('refresh', secondary_keys)

    def test_v2_authenticated_tablet_nav_does_not_render_login_cta_for_logged_in_user(self):
        self._login('tabletnav')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertNotIn('fa-user-lock', content)
        self.assertIn('tabletnav님', content)

    def test_v2_context_sections_count(self):
        """V2 컨텍스트에 sections 존재"""
        response = self.client.get(reverse('home'))
        sections = response.context.get('sections', [])
        self.assertGreaterEqual(len(sections), 2)

    def test_v2_context_quick_actions_max_5(self):
        """V2 퀵 액션 최대 5개"""
        self._login('maxuser')
        response = self.client.get(reverse('home'))
        quick_actions = response.context.get('quick_actions', [])
        self.assertLessEqual(len(quick_actions), 5)
        self.assertGreaterEqual(len(quick_actions), 1)

    def test_v2_has_global_service_launcher_trigger(self):
        """V2 홈은 전역 상단바 런처 트리거를 사용"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-global-service-launcher-trigger="true"', content)
        self.assertIn('서비스 찾기', content)
        self.assertNotIn('서비스 검색...', content)
        self.assertNotIn('slice(0, 8)', content)
        self.assertNotIn('window.openModal(p.id)', content)
        self.assertIn('id="service-launcher-items-data"', content)
        self.assertIn('core/js/base.js', content)

    def test_v2_service_launcher_json_in_context(self):
        """V2 홈에 service_launcher_json 컨텍스트 존재"""
        response = self.client.get(reverse('home'))
        self.assertIn('service_launcher_json', response.context)

    @override_settings(SHEETBOOK_DISCOVERY_VISIBLE=False)
    def test_v2_home_hides_sheetbook_from_discovery_surfaces(self):
        hidden_product = self._create_sheetbook_product()
        user = self._login('sheetbookhiddenv2')
        ProductFavorite.objects.create(user=user, product=hidden_product, pin_order=1)
        ProductUsageLog.objects.create(user=user, product=hidden_product, action='launch', source='home_quick')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertNotIn('숨김 교무수첩', content)
        self.assertNotIn(hidden_product.id, [item['product'].id for item in response.context.get('quick_actions', [])])
        self.assertNotIn(hidden_product.id, [item['product'].id for item in response.context.get('favorite_items', [])])
        self.assertNotIn(hidden_product.id, [item['product'].id for item in response.context.get('recent_items', [])])
        self.assertNotIn(hidden_product.id, [item['product'].id for item in response.context.get('discovery_items', [])])
        self.assertNotIn(hidden_product.id, [item['product'].id for item in response.context.get('companion_items', [])])
        section_product_ids = []
        for section in response.context.get('sections', []):
            section_product_ids.extend(product.id for product in section.get('products', []))
            section_product_ids.extend(product.id for product in section.get('overflow_products', []))
        for section in response.context.get('aux_sections', []):
            section_product_ids.extend(product.id for product in section.get('products', []))
            section_product_ids.extend(product.id for product in section.get('overflow_products', []))
        self.assertNotIn(hidden_product.id, section_product_ids)
        self.assertNotIn(hidden_product.id, [product.id for product in response.context.get('games', [])])
        search_payload = json.loads(response.context['service_launcher_json'])
        self.assertNotIn('숨김 교무수첩', [item['title'] for item in search_payload])

    def test_v2_authenticated_top_favorites_use_compact_title_only_cards(self):
        user = self._login('favoritecompact')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        favorites_index = content.index('data-home-v2-top-favorites="true"')
        calendar_index = content.index('data-home-v2-top-calendar="true"')
        favorites_block = content[favorites_index:calendar_index]

        self.assertIn('data-home-v2-top-favorites-grid="true"', favorites_block)
        self.assertIn('data-home-v2-favorite-card="true"', favorites_block)
        self.assertNotIn('자주 쓰는 서비스만 가까이에 둡니다.', favorites_block)
        self.assertNotIn('data-home-v2-favorite-card-body="true"', favorites_block)
        self.assertNotIn('수업을 준비해요', favorites_block)

    def test_v2_authenticated_top_favorites_use_compact_aliases_with_full_title_tooltips(self):
        user = self._login('favoritealiases')
        sparkling_board = Product.objects.create(
            title="반짝반짝 우리반 알림판",
            description="학급 소식",
            price=0,
            is_active=True,
            service_type='classroom',
        )
        reservation_system = Product.objects.create(
            title="학교 예약 시스템",
            description="특별실 예약",
            price=0,
            is_active=True,
            service_type='work',
        )
        seed_quiz = Product.objects.create(
            title="씨앗 퀴즈",
            description="퀴즈 만들기",
            price=0,
            is_active=True,
            service_type='game',
        )
        ProductFavorite.objects.create(user=user, product=sparkling_board, pin_order=1)
        ProductFavorite.objects.create(user=user, product=reservation_system, pin_order=2)
        ProductFavorite.objects.create(user=user, product=seed_quiz, pin_order=3)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        favorites_index = content.index('data-home-v2-top-favorites="true"')
        calendar_index = content.index('data-home-v2-top-calendar="true"')
        favorites_block = content[favorites_index:calendar_index]

        self.assertIn('title="반짝반짝 우리반 알림판">알림판</p>', favorites_block)
        self.assertIn('aria-label="반짝반짝 우리반 알림판 즐겨찾기 토글"', favorites_block)
        self.assertIn('title="학교 예약 시스템">학교 예약</p>', favorites_block)
        self.assertIn('title="씨앗 퀴즈">씨앗 퀴즈</p>', favorites_block)

    def test_build_favorite_service_title_prefers_head_nouns_for_decorated_names(self):
        self.assertEqual(build_favorite_service_title("반짝반짝 우리반 알림판"), "알림판")
        self.assertEqual(build_favorite_service_title("가뿐하게 서명 톡"), "서명")
        self.assertEqual(build_favorite_service_title("두뇌 풀가동! 교실 체스"), "체스")
        self.assertEqual(build_favorite_service_title("두뇌 풀가동! 교실 장기"), "장기")
        self.assertEqual(build_favorite_service_title("왁자지껄 교실 윷놀이"), "윷놀이")
        self.assertEqual(build_favorite_service_title("글솜씨 뚝딱! 소식지"), "소식지")
        self.assertEqual(build_favorite_service_title("학교 예약 시스템"), "학교 예약")

    @override_settings(SHEETBOOK_ENABLED=True, SHEETBOOK_DISCOVERY_VISIBLE=False)
    def test_v2_workspace_context_disabled_when_sheetbook_discovery_hidden(self):
        from sheetbook.models import Sheetbook, SheetbookMetricEvent

        user = self._login('workspacehidden')
        Sheetbook.objects.create(owner=user, title='비노출 수첩', academic_year=2026)

        response = self.client.get(reverse('home'))

        self.assertFalse(response.context['sheetbook_workspace']['enabled'])
        self.assertFalse(
            SheetbookMetricEvent.objects.filter(
                user=user,
                event_name='workspace_home_opened',
            ).exists()
        )

    @override_settings(SHEETBOOK_ENABLED=True, SHEETBOOK_DISCOVERY_VISIBLE=True)
    def test_v2_workspace_context_enabled_when_sheetbook_discovery_visible(self):
        from sheetbook.models import Sheetbook, SheetbookMetricEvent

        user = self._login('workspacevisible')
        Sheetbook.objects.create(owner=user, title='노출 수첩', academic_year=2026)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertTrue(response.context['sheetbook_workspace']['enabled'])
        self.assertGreaterEqual(len(response.context['sheetbook_workspace']['recent_sheetbooks']), 1)
        self.assertTrue(
            SheetbookMetricEvent.objects.filter(
                user=user,
                event_name='workspace_home_opened',
            ).exists()
        )
        self.assertNotIn('교무수첩 워크스페이스', content)

    def test_v2_usage_based_quick_actions(self):
        """V2 사용 기록 기반 퀵 액션 반영"""
        from core.models import ProductUsageLog
        user = self._login('usageuser')
        # p2(행정 도구)를 많이 사용
        for _ in range(5):
            ProductUsageLog.objects.create(user=user, product=self.p2, action='launch', source='home_quick')
        response = self.client.get(reverse('home'))
        quick_actions = response.context.get('quick_actions', [])
        # 가장 많이 사용한 p2가 첫 번째
        self.assertEqual(quick_actions[0]['product'].id, self.p2.id)


    def test_v2_quick_action_prefers_launch_route_name(self):
        self.p2.launch_route_name = 'collect:landing'
        self.p2.save(update_fields=['launch_route_name'])

        self._login('routeuser')
        response = self.client.get(reverse('home'))
        quick_actions = response.context.get('quick_actions', [])
        p2_action = next((item for item in quick_actions if item['product'].id == self.p2.id), None)

        self.assertIsNotNone(p2_action)
        self.assertEqual(p2_action['href'], reverse('collect:landing'))
        self.assertFalse(p2_action['is_external'])

    def test_v2_sections_are_preview_capped(self):
        Product.objects.create(
            title="Classroom Extra 1",
            description="extra",
            price=0,
            is_active=True,
            service_type='classroom',
        )
        Product.objects.create(
            title="Classroom Extra 2",
            description="extra",
            price=0,
            is_active=True,
            service_type='classroom',
        )

        response = self.client.get(reverse('home'))
        sections = response.context.get('sections', [])
        class_ops = next((section for section in sections if section.get('key') == 'class_ops'), None)

        self.assertIsNotNone(class_ops)
        self.assertLessEqual(len(class_ops['products']), 2)
        self.assertGreaterEqual(class_ops['total_count'], len(class_ops['products']))
        self.assertEqual(class_ops['remaining_count'], class_ops['total_count'] - len(class_ops['products']))

    def test_v2_section_more_toggle_renders_when_overflow_exists(self):
        Product.objects.create(
            title="Classroom Extra 1",
            description="extra",
            price=0,
            is_active=True,
            service_type='classroom',
        )
        Product.objects.create(
            title="Classroom Extra 2",
            description="extra",
            price=0,
            is_active=True,
            service_type='classroom',
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-home-v2-section-more-toggle="true"', content)
        self.assertIn('전체 보기', content)
        self.assertNotIn('href="/products/?section=', content)

    def test_v2_section_overflow_items_are_rendered_in_markup(self):
        Product.objects.create(
            title="Classroom Overflow A",
            description="extra",
            price=0,
            is_active=True,
            service_type='classroom',
        )
        Product.objects.create(
            title="Classroom Overflow B",
            description="extra",
            price=0,
            is_active=True,
            service_type='classroom',
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('Classroom Overflow A', content)
        self.assertIn('Classroom Overflow B', content)

    def test_v2_authenticated_tablet_summary_uses_richer_preview_cards(self):
        author = _create_onboarded_user('tabletcommunityauthor')
        Post.objects.create(
            author=author,
            content='학급 운영 팁을 공유합니다.',
            post_type='news_link',
            source_url='https://example.com/community',
            og_title='이번 주 소통 요약',
            og_description='중요한 공지와 최근 이야기를 먼저 확인하세요.',
            og_image_url='https://example.com/community.jpg',
            publisher='테스트 매체',
        )

        self._login('tabletcommunityuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-v2-tablet-community-summary="true"', content)
        self.assertIn('data-home-v2-tablet-community-card="true"', content)
        self.assertIn('https://example.com/community.jpg', content)

    def test_v2_uses_xl_breakpoint_for_sns_sidebar(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('hidden xl:block', content)
        self.assertIn('block xl:hidden', content)

    def test_v2_authenticated_uses_xl_breakpoint_for_sns_sidebar(self):
        self._login('breakpointuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('hidden xl:block', content)
        self.assertIn('block xl:hidden', content)
        self.assertIn('data-home-v2-top-zone="true"', content)

    def test_v2_staff_home_restores_sns_controls(self):
        staff = _create_onboarded_user('staffsns', nickname='운영자')
        staff.is_staff = True
        staff.save(update_fields=['is_staff'])
        self.client.login(username='staffsns', password='pass1234')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('실시간 소통', content)
        self.assertIn('공지 작성', content)
        self.assertIn('뉴스 검토', content)
        self.assertIn('인사이트 노출', content)
        self.assertIn('data-home-v2-top-calendar="true"', content)

    def test_v2_notice_scope_excludes_news_link_cards(self):
        author = _create_onboarded_user('noticeauthor')
        Post.objects.create(author=author, content='공지 본문', post_type='notice')
        Post.objects.create(
            author=author,
            content='뉴스 본문',
            post_type='news_link',
            source_url='https://example.com/news',
            og_title='뉴스 제목',
            og_image_url='https://example.com/news.jpg',
            publisher='테스트 매체',
        )

        response = self.client.get(reverse('home'), {'feed_scope': 'notice'})
        content = response.content.decode('utf-8')

        self.assertIn('공지 본문', content)
        self.assertNotIn('뉴스 제목', content)
        self.assertNotIn('원문 보기 (새 탭)', content)

    def test_v2_feed_renders_news_link_preview_image(self):
        author = _create_onboarded_user('newsauthor')
        Post.objects.create(
            author=author,
            content='뉴스 요약',
            post_type='news_link',
            source_url='https://example.com/article',
            og_title='교실 뉴스',
            og_description='학급 운영에 도움이 되는 기사입니다.',
            og_image_url='https://example.com/article.jpg',
            publisher='테스트 매체',
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('교실 뉴스', content)
        self.assertIn('https://example.com/article.jpg', content)
        self.assertIn('원문 보기 (새 탭)', content)
    def test_v2_mobile_sns_more_uses_toggle_not_anchor(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('@click="snsOpen = true"', content)
        self.assertNotIn('hx-select="#mobile-post-list-container"', content)
        self.assertNotIn('href="#sns-full-section-v2"', content)

    def test_v2_authenticated_mobile_sns_more_uses_toggle_not_anchor(self):
        self._login('v2authsns')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('@click="snsOpen = true"', content)
        self.assertNotIn('hx-select="#mobile-post-list-container"', content)
        self.assertNotIn('href="#sns-full-section-auth-v2"', content)

    def test_v2_home_sns_shows_expand_button_after_three_posts(self):
        _create_posts()

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-sns-expand="true"', content)
        self.assertEqual(content.count('aria-label="소통 글 상세 보기"'), 3)
        self.assertIn('compact_posts=1', content)

    def test_v2_home_htmx_post_feed_keeps_compact_expand_button(self):
        _create_posts(username='snshtmxauthor')

        response = self.client.get(
            reverse('home'),
            {'target': 'post-list-container', 'compact_posts': '1'},
            HTTP_HX_REQUEST='true',
        )
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('data-home-sns-expand="true"', content)
        self.assertIn('이전 글 더 보기', content)

    def test_v2_community_feed_keeps_full_sns_list_without_home_expand_button(self):
        _create_posts(username='snscommunityauthor')

        response = self.client.get(reverse('community_feed'))
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('data-home-sns-expand="true"', content)
        self.assertNotIn('compact_posts=1', content)


@override_settings(HOME_LAYOUT_VERSION='v3')
class HomeV3ViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.p1 = Product.objects.create(
            title="수업 도구", description="수업용", price=0,
            is_active=True, service_type='classroom', is_featured=True,
            solve_text='수업을 준비해요',
        )
        self.p2 = Product.objects.create(
            title="행정 도구", description="행정용", price=0,
            is_active=True, service_type='work',
        )
        self.p3 = Product.objects.create(
            title="테스트 게임", description="게임", price=0,
            is_active=True, service_type='game',
        )

    def _login(self, username='v3user', nickname=None):
        user = _create_onboarded_user(username, nickname=nickname)
        self.client.login(username=username, password='pass1234')
        return user

    def test_v3_flag_falls_back_to_v2_anonymous_surface(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('로그인하고 시작하기', content)
        self.assertIn('수합·서명', content)
        self.assertNotIn('id="primary-zone"', content)

    def test_v3_flag_falls_back_to_v2_authenticated_layout(self):
        self._login('v3slots')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-v2-top-zone="true"', content)
        self.assertIn('data-home-v2-top-calendar="true"', content)
        self.assertIn('hidden xl:block', content)
        self.assertIn('block xl:hidden', content)
        self.assertNotIn('id="primary-zone"', content)

    def test_community_feed_uses_separate_full_screen_surface(self):
        response = self.client.get(reverse('community_feed'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '실시간 소통')
        self.assertContains(response, '홈에서는 요약만 보고')

    def test_v3_flag_uses_real_calendar_and_compact_service_cards(self):
        self._login('v3calendar')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('학급 캘린더', content)
        self.assertIn('home-calendar-day', content)
        self.assertIn('data-home-v2-service-card="true"', content)
        self.assertNotIn('개인 캘린더', content)
        self.assertNotIn('수업 도구 상세 설명 열기', content)

    def test_v3_search_payload_hides_sheetbook_and_uses_calendar_public_name(self):
        Product.objects.create(
            title="교무수첩",
            description="교무수첩 설명",
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='classcalendar:main',
        )
        Product.objects.create(
            title="교무수첩",
            description="기록 도구",
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='sheetbook:index',
        )

        response = self.client.get(reverse('home'))
        payload = json.loads(response.context['service_launcher_json'])
        titles = [item['title'] for item in payload]

        self.assertIn('학급 캘린더', titles)
        self.assertNotIn('교무수첩', titles)
        self.assertNotIn('학급 기록 보드', titles)


class PromptLabViewTest(TestCase):
    def test_prompt_lab_page_uses_shared_catalog_script(self):
        response = self.client.get(reverse('prompt_lab'))
        content = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="prompt-lab-catalog"', content)
        self.assertIn("window.initPromptLabPage({ catalogScriptId: 'prompt-lab-catalog' });", content)
        self.assertIn('core/js/prompt_lab.js', content)


class HomePlacementPlannerTest(TestCase):
    def test_planner_places_starter_before_two_quick_cards(self):
        entries = [
            {
                'key': 'qrgen',
                'title': 'QR',
                'home_surface': HOME_SURFACE_ACTION,
                'layout_kind': HOME_LAYOUT_QUICK,
                'home_priority': 20,
                'full_url': '/qr/',
                'overflow_behavior': HOME_OVERFLOW_PROMOTE,
                'fields': ('url',),
                'preview_kind': 'qr',
            },
            {
                'key': 'noticegen',
                'title': 'Notice',
                'home_surface': HOME_SURFACE_ACTION,
                'layout_kind': HOME_LAYOUT_STARTER,
                'home_priority': 10,
                'full_url': '/notice/',
                'overflow_behavior': HOME_OVERFLOW_PROMOTE,
                'fields': ('target', 'topic', 'keywords'),
                'preview_kind': 'text',
            },
            {
                'key': 'prompt_lab',
                'title': 'Prompt',
                'home_surface': HOME_SURFACE_ACTION,
                'layout_kind': HOME_LAYOUT_QUICK,
                'home_priority': 30,
                'full_url': '/prompts/',
                'overflow_behavior': HOME_OVERFLOW_PROMOTE,
                'fields': ('category',),
                'preview_kind': 'text',
            },
        ]

        planned = plan_home_action_surface(entries)

        self.assertEqual([entry['key'] for entry in planned], ['noticegen', 'qrgen', 'prompt_lab'])
        self.assertEqual(planned[0]['render_variant'], 'starter')
        self.assertEqual(planned[0]['span'], 2)
        self.assertEqual(planned[1]['render_variant'], 'quick')
        self.assertEqual(planned[2]['render_variant'], 'quick')

    def test_planner_promotes_last_quick_card_when_count_is_odd(self):
        entries = [
            {
                'key': 'quick-a',
                'title': 'A',
                'home_surface': HOME_SURFACE_ACTION,
                'layout_kind': HOME_LAYOUT_QUICK,
                'home_priority': 10,
                'full_url': '/a/',
                'overflow_behavior': HOME_OVERFLOW_PROMOTE,
                'fields': ('field-a',),
                'preview_kind': 'text',
            },
            {
                'key': 'quick-b',
                'title': 'B',
                'home_surface': HOME_SURFACE_ACTION,
                'layout_kind': HOME_LAYOUT_QUICK,
                'home_priority': 20,
                'full_url': '/b/',
                'overflow_behavior': HOME_OVERFLOW_PROMOTE,
                'fields': ('field-b',),
                'preview_kind': 'text',
            },
            {
                'key': 'quick-c',
                'title': 'C',
                'home_surface': HOME_SURFACE_ACTION,
                'layout_kind': HOME_LAYOUT_QUICK,
                'home_priority': 30,
                'full_url': '/c/',
                'overflow_behavior': HOME_OVERFLOW_PROMOTE,
                'fields': ('field-c',),
                'preview_kind': 'text',
            },
        ]

        planned = plan_home_action_surface(entries)

        self.assertEqual([entry['render_variant'] for entry in planned], ['quick', 'quick', 'quick-wide'])
        self.assertEqual(planned[-1]['span'], 2)

    def test_planner_excludes_non_action_and_excluded_layout_entries(self):
        entries = [
            {
                'key': 'community',
                'title': 'Community',
                'home_surface': HOME_SURFACE_CONTENT,
                'layout_kind': HOME_LAYOUT_QUICK,
                'home_priority': 10,
                'full_url': '/community/',
                'overflow_behavior': HOME_OVERFLOW_PROMOTE,
            },
            {
                'key': 'excluded',
                'title': 'Excluded',
                'home_surface': HOME_SURFACE_ACTION,
                'layout_kind': HOME_LAYOUT_EXCLUDED,
                'home_priority': 20,
                'full_url': '/excluded/',
                'overflow_behavior': HOME_OVERFLOW_PROMOTE,
            },
        ]

        self.assertEqual(plan_home_action_surface(entries), [])

    def test_planner_excludes_quick_cards_that_break_field_contract(self):
        entries = [
            {
                'key': 'quick-overflow',
                'title': 'Overflow',
                'home_surface': HOME_SURFACE_ACTION,
                'layout_kind': HOME_LAYOUT_QUICK,
                'home_priority': 10,
                'full_url': '/overflow/',
                'overflow_behavior': HOME_OVERFLOW_PROMOTE,
                'fields': ('a', 'b', 'c'),
                'preview_kind': 'text',
            },
        ]

        self.assertEqual(plan_home_action_surface(entries), [])

    def test_planner_excludes_invalid_preview_contracts(self):
        entries = [
            {
                'key': 'starter-long-preview',
                'title': 'Starter',
                'home_surface': HOME_SURFACE_ACTION,
                'layout_kind': HOME_LAYOUT_STARTER,
                'home_priority': 10,
                'full_url': '/starter/',
                'overflow_behavior': HOME_OVERFLOW_PROMOTE,
                'fields': ('a', 'b', 'c'),
                'preview_kind': 'long-text',
            },
        ]

        self.assertEqual(plan_home_action_surface(entries), [])


@override_settings(HOME_V2_ENABLED=True)
class TrackUsageAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(
            title="테스트 서비스", description="설명", price=0,
            is_active=True, service_type='classroom',
        )

    def _login(self, username='apiuser'):
        user = _create_onboarded_user(username)
        self.client.login(username=username, password='pass1234')
        return user

    def test_track_usage_anonymous_ignored(self):
        """비로그인 사용자 추적 무시"""
        import json
        response = self.client.post(
            reverse('track_product_usage'),
            data=json.dumps({'product_id': self.product.id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_track_usage_authenticated(self):
        """로그인 사용자 사용 기록 생성"""
        from core.models import ProductUsageLog
        import json
        self._login('trackuser')
        response = self.client.post(
            reverse('track_product_usage'),
            data=json.dumps({'product_id': self.product.id, 'action': 'launch', 'source': 'home_quick'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProductUsageLog.objects.filter(user__username='trackuser').count(), 1)

    def test_track_usage_invalid_product(self):
        """존재하지 않는 서비스 ID는 404"""
        import json
        self._login('invaliduser')
        response = self.client.post(
            reverse('track_product_usage'),
            data=json.dumps({'product_id': 99999}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
