import json

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from core.teacher_first_cards import build_favorite_service_title
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

    def test_home_authenticated_200(self):
        """로그인 홈 200 응답"""
        _create_onboarded_user('testuser')
        self.client.login(username='testuser', password='pass1234')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_v1_search_products_json_in_context(self):
        """V1 홈에서도 글로벌 검색 컨텍스트를 제공"""
        response = self.client.get(reverse('home'))
        self.assertIn('search_products_json', response.context)

    @override_settings(SHEETBOOK_DISCOVERY_VISIBLE=False)
    def test_v1_home_hides_sheetbook_product_when_discovery_disabled(self):
        self._create_sheetbook_product()

        response = self.client.get(reverse('home'))
        product_titles = [product.title for product in response.context['products']]

        self.assertNotIn('숨김 교무수첩', product_titles)
        self.assertNotContains(response, '숨김 교무수첩')

    @override_settings(SHEETBOOK_DISCOVERY_VISIBLE=False)
    def test_v1_search_products_json_hides_sheetbook_when_discovery_disabled(self):
        self._create_sheetbook_product()

        response = self.client.get(reverse('home'))
        payload = json.loads(response.context['search_products_json'])
        titles = [item['title'] for item in payload]

        self.assertNotIn('숨김 교무수첩', titles)

    @override_settings(GLOBAL_SEARCH_ENABLED=False)
    def test_search_products_json_absent_when_global_search_disabled(self):
        """글로벌 검색 비활성화 시 컨텍스트에서 검색 데이터 제외"""
        response = self.client.get(reverse('home'))
        self.assertNotIn('search_products_json', response.context)

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

    def _create_home_mini_products(self):
        notice = Product.objects.create(
            title="알림장 & 주간학습 멘트 생성기",
            description="안내문 작성",
            price=0,
            is_active=True,
            service_type='work',
            launch_route_name='noticegen:main',
            icon='fa-solid fa-note-sticky',
        )
        qr = Product.objects.create(
            title="수업 QR 생성기",
            description="QR 생성",
            price=0,
            is_active=True,
            is_guest_allowed=True,
            service_type='classroom',
            launch_route_name='qrgen:landing',
            icon='fa-solid fa-qrcode',
        )
        prompt = Product.objects.create(
            title="AI 프롬프트 레시피",
            description="프롬프트 추천",
            price=0,
            is_active=True,
            is_guest_allowed=True,
            service_type='edutech',
            launch_route_name='prompt_lab',
            icon='fa-solid fa-wand-magic-sparkles',
        )
        message = Product.objects.create(
            title="메시지 저장",
            description="메시지 보관함",
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='classcalendar:main',
            icon='fa-solid fa-box-archive',
        )
        return notice, qr, prompt, message

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

    def test_v2_anonymous_does_not_render_today_try_now_section(self):
        self._create_home_mini_products()

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertNotIn('data-home-v2-try-now="true"', content)
        self.assertNotIn('data-home-v2-try-now-grid="true"', content)

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
        self.assertIn('studentGamesQrModal', content)
        self.assertIn('data-student-games-issue-url="/products/dutyticker/student-games/issue/"', content)
        self.assertNotIn('launch/?token=', content)

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

    def test_v2_authenticated_uses_compact_top_zone_without_large_greeting(self):
        """V2 로그인 홈은 큰 인사말 대신 상단 3블록을 사용"""
        self._login('greetuser', nickname='홍길동')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertNotIn('선생님, 안녕하세요', content)
        self.assertIn('data-home-v2-top-zone="true"', content)
        self.assertIn('openSearchModal', content)

    def test_v2_authenticated_orders_top_zone_services_and_sns_summary(self):
        self._login('zoneuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        top_zone_index = content.index('data-home-v2-top-zone="true"')
        today_index = content.index('data-home-v2-top-today="true"')
        favorites_index = content.index('data-home-v2-top-favorites="true"')
        calendar_index = content.index('data-home-v2-top-calendar="true"')
        services_index = content.index('data-home-v2-service-groups="true"')
        sns_index = content.index('data-home-v2-sns-summary="true"')

        self.assertLess(top_zone_index, services_index)
        self.assertLess(services_index, sns_index)
        self.assertLess(today_index, favorites_index)
        self.assertLess(favorites_index, calendar_index)

    def test_v2_authenticated_has_sections(self):
        """V2 로그인 홈에 목적별 섹션 존재"""
        self._login('secuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('수합·서명', content)
        self.assertIn('문서·작성', content)
        self.assertIn('data-home-v2-service-grid="true"', content)

    def test_v2_authenticated_places_single_today_try_now_section_between_top_zone_and_service_groups(self):
        notice, qr, prompt, message = self._create_home_mini_products()
        self._login('trynowuser')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        top_zone_index = content.index('data-home-v2-top-zone="true"')
        try_now_index = content.index('data-home-v2-try-now="true"')
        services_index = content.index('data-home-v2-service-groups="true"')
        try_now_markup = content[try_now_index:services_index]

        self.assertLess(top_zone_index, try_now_index)
        self.assertLess(try_now_index, services_index)
        self.assertEqual(content.count('data-home-v2-try-now="true"'), 1)
        self.assertIn('data-home-mini-root="true"', try_now_markup)
        self.assertIn(f'data-product-id="{notice.id}"', try_now_markup)
        self.assertIn(f'data-product-id="{qr.id}"', try_now_markup)
        self.assertIn(f'data-product-id="{prompt.id}"', try_now_markup)
        self.assertIn(f'data-product-id="{message.id}"', try_now_markup)
        self.assertIn('알림장·주간학습 멘트 생성기', try_now_markup)
        self.assertIn('수업 QR 생성기', try_now_markup)
        self.assertIn('AI 프롬프트 레시피', try_now_markup)
        self.assertIn('메시지 저장', try_now_markup)
        self.assertIn('data-home-v2-try-now-grid="true"', try_now_markup)
        self.assertIn('data-home-mini-card="notice"', try_now_markup)
        self.assertIn('data-home-mini-card="qr"', try_now_markup)
        self.assertIn('data-home-mini-card="prompt"', try_now_markup)
        self.assertIn('data-home-mini-card="message"', try_now_markup)
        self.assertIn('data-home-mini-submit="notice"', try_now_markup)
        self.assertIn('data-home-mini-submit="qr"', try_now_markup)
        self.assertIn('data-home-mini-submit="prompt"', try_now_markup)
        self.assertIn('data-home-mini-submit="message"', try_now_markup)
        self.assertIn(f'data-base-href="{reverse("noticegen:main")}"', try_now_markup)
        self.assertIn(f'data-base-href="{reverse("qrgen:landing")}"', try_now_markup)
        self.assertIn(f'data-base-href="{reverse("prompt_lab")}"', try_now_markup)
        self.assertIn(f'data-base-href="{reverse("classcalendar:main")}?panel=message-archive"', try_now_markup)
        self.assertIn('home-prompt-recipe-catalog-data', content)
        self.assertIn('md:grid-cols-2', try_now_markup)
        self.assertNotIn('overflow-x-auto', try_now_markup)
        self.assertNotIn('quick-scroll', try_now_markup)
        self.assertNotIn('data-home-v2-try-now-support-grid="true"', try_now_markup)
        self.assertNotIn('data-home-v2-try-now-card="support"', try_now_markup)

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
        self.assertIn(f'data-product-id="{self.p1.id}"', content)

    def test_v2_service_card_uses_title_body_and_favorite_contract(self):
        """V2 서비스 카드는 제목/본문/즐겨찾기만 전면 노출"""
        self._login('carduser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-home-v2-service-card="true"', content)
        self.assertIn('수업 도구', content)
        self.assertIn('수업을 준비해요', content)
        self.assertIn('data-favorite-toggle="true"', content)

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

    def test_v2_has_search_button(self):
        """V2 홈에 검색 버튼 존재"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('openSearchModal', content)

    def test_v2_search_products_json_in_context(self):
        """V2 홈에 search_products_json 컨텍스트 존재"""
        response = self.client.get(reverse('home'))
        self.assertIn('search_products_json', response.context)

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
        search_payload = json.loads(response.context['search_products_json'])
        self.assertNotIn('숨김 교무수첩', [item['title'] for item in search_payload])

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

        self.assertTrue(response.context['sheetbook_workspace']['enabled'])
        self.assertGreaterEqual(len(response.context['sheetbook_workspace']['recent_sheetbooks']), 1)
        self.assertTrue(
            SheetbookMetricEvent.objects.filter(
                user=user,
                event_name='workspace_home_opened',
            ).exists()
        )

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
        self.assertLessEqual(len(class_ops['products']), 3)
        self.assertGreaterEqual(class_ops['total_count'], len(class_ops['products']))
        self.assertEqual(class_ops['remaining_count'], class_ops['total_count'] - len(class_ops['products']))

    def test_v2_section_overflow_items_render_in_compact_grid_without_toggle(self):
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
        self.assertIn('Classroom Extra 1', content)
        self.assertIn('Classroom Extra 2', content)
        self.assertIn('data-home-v2-service-grid="true"', content)
        self.assertNotIn('data-track="section_more_toggle"', content)

    def test_v2_authenticated_removes_legacy_sidebar_and_wide_today_markup(self):
        self._login('breakpointuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertNotIn('hidden xl:block', content)
        self.assertNotIn('block xl:hidden', content)
        self.assertNotIn('개인 캘린더', content)
        self.assertNotIn('@click="snsOpen = true"', content)
        self.assertNotIn('lg:grid-cols-2', content)

    def test_v2_staff_home_shows_compact_sns_controls(self):
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

    def test_v2_authenticated_top_favorites_empty_state_has_no_recommendation_fallback(self):
        self._login('favoriteempty')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('별표한 서비스가 여기에 모입니다.', content)
        self.assertNotIn('추천 빠른 실행', content)

    def test_v2_authenticated_top_favorites_use_compact_title_only_cards(self):
        user = self._login('favoritecompact')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        favorites_index = content.index('data-home-v2-top-favorites="true"')
        calendar_index = content.index('data-home-v2-top-calendar="true"')
        favorites_block = content[favorites_index:calendar_index]

        self.assertIn('data-home-v2-top-favorites-grid="true"', favorites_block)
        self.assertIn('data-home-v2-top-favorite-card="true"', favorites_block)
        self.assertNotIn('자주 쓰는 서비스만 짧게 모아 둡니다.', favorites_block)
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

        self.assertIn('title="반짝반짝 우리반 알림판">알림판</span>', favorites_block)
        self.assertIn('aria-label="반짝반짝 우리반 알림판 즐겨찾기 토글"', favorites_block)
        self.assertIn('title="학교 예약 시스템">학교 예약</span>', favorites_block)
        self.assertIn('title="씨앗 퀴즈">씨앗 퀴즈</span>', favorites_block)

    def test_build_favorite_service_title_prefers_head_nouns_for_decorated_names(self):
        self.assertEqual(build_favorite_service_title("반짝반짝 우리반 알림판"), "알림판")
        self.assertEqual(build_favorite_service_title("가뿐하게 서명 톡"), "서명")
        self.assertEqual(build_favorite_service_title("두뇌 풀가동! 교실 체스"), "체스")
        self.assertEqual(build_favorite_service_title("두뇌 풀가동! 교실 장기"), "장기")
        self.assertEqual(build_favorite_service_title("왁자지껄 교실 윷놀이"), "윷놀이")
        self.assertEqual(build_favorite_service_title("글솜씨 뚝딱! 소식지"), "소식지")
        self.assertEqual(build_favorite_service_title("학교 예약 시스템"), "학교 예약")

    def test_v2_calendar_card_uses_public_name_and_hides_sheetbook_copy(self):
        self._login('calendaruser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('학급 캘린더', content)
        self.assertIn('일정 빠른 추가', content)
        self.assertIn('일정 추가', content)
        self.assertNotIn('교무수첩', content)
        self.assertNotIn('개인 캘린더', content)

    def test_v2_notice_scope_excludes_news_in_sns_summary(self):
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

        self._login('noticeviewer')
        response = self.client.get(reverse('home'), {'feed_scope': 'notice'})
        content = response.content.decode('utf-8')

        self.assertIn('공지 본문', content)
        self.assertNotIn('뉴스 제목', content)
        self.assertNotIn('원문 보기 (새 탭)', content)

    def test_v2_feed_summary_renders_news_link_preview_image(self):
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

        self._login('newssummary')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('교실 뉴스', content)
        self.assertIn('https://example.com/article.jpg', content)
        self.assertIn('data-home-v2-sns-summary="true"', content)

    def test_v2_mobile_sns_more_uses_toggle_not_anchor(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('@click="snsOpen = true"', content)
        self.assertNotIn('hx-select="#mobile-post-list-container"', content)
        self.assertNotIn('href="#sns-full-section-v2"', content)

class HomeSupplementaryViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_community_feed_uses_separate_full_screen_surface(self):
        response = self.client.get(reverse('community_feed'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '실시간 소통')
        self.assertContains(response, '홈에서는 요약만 보고')

    def test_home_search_payload_hides_sheetbook_and_uses_calendar_public_name(self):
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
        payload = json.loads(response.context['search_products_json'])
        titles = [item['title'] for item in payload]

        self.assertIn('학급 캘린더', titles)
        self.assertNotIn('교무수첩', titles)
        self.assertNotIn('학급 기록 보드', titles)



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
