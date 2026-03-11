import json

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from products.models import Product, ServiceManual
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
        self.assertIn('openSearchModal', content)

    def test_v2_authenticated_has_quick_actions(self):
        """V2 로그인 홈에 퀵 액션 존재"""
        self._login('qauser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-track="quick_action"', content)
        self.assertIn('추천 빠른 실행', content)

    def test_v2_authenticated_has_sections(self):
        """V2 로그인 홈에 목적별 섹션 존재"""
        self._login('secuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('수합·서명', content)
        self.assertIn('문서·작성', content)

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

    def test_v2_mini_card_shows_solve_text(self):
        """V2 미니 카드에 solve_text 표시"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('수업을 준비해요', content)

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
        self.assertIn('data-track="section_more_toggle"', content)
        self.assertIn('더보기', content)

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

    def test_v3_anonymous_uses_shared_slot_order(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        primary_index = content.index('id="primary-zone"')
        discovery_index = content.index('id="discovery-sections"')
        secondary_index = content.index('id="secondary-sections"')

        self.assertLess(primary_index, discovery_index)
        self.assertLess(discovery_index, secondary_index)

    def test_v3_authenticated_uses_shared_slot_order(self):
        self._login('v3slots')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        primary_index = content.index('id="primary-zone"')
        discovery_index = content.index('id="discovery-sections"')
        secondary_index = content.index('id="secondary-sections"')

        self.assertLess(primary_index, discovery_index)
        self.assertLess(discovery_index, secondary_index)

    def test_v3_authenticated_orders_today_calendar_and_related_shortcuts(self):
        self._login('v3sns')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        today_index = content.index('data-home-v3-today="true"')
        calendar_hub_index = content.index('data-home-v3-calendar-hub="true"')
        related_index = content.index('data-home-v3-related-shortcuts="true"')

        self.assertLess(today_index, calendar_hub_index)
        self.assertLess(calendar_hub_index, related_index)

    def test_v3_moves_sns_into_secondary_summary_panel(self):
        self._login('v3snssecondary')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('전체 소통 보기', content)
        self.assertNotIn('hidden xl:block', content)
        self.assertNotIn('block xl:hidden', content)
        self.assertIn('Community Summary', content)
        self.assertIn(reverse('community_feed'), content)
        self.assertNotIn('data-home-v3-sns-toggle', content)

    def test_v3_authenticated_has_single_related_shortcuts_block(self):
        self._login('v3quick')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertEqual(content.count('data-home-v3-related-shortcuts="true"'), 1)
        self.assertIn('관련 바로가기', content)
        self.assertNotIn('추천 빠른 실행', content)

    def test_community_feed_uses_separate_full_screen_surface(self):
        response = self.client.get(reverse('community_feed'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '실시간 소통')
        self.assertContains(response, '홈에서는 요약만 보고')

    @override_settings(SHEETBOOK_ENABLED=False)
    def test_v3_calendar_hub_keeps_record_board_flow_hidden_when_sheetbook_disabled(self):
        self._login('v3sheetbookoff')
        response = self.client.get(reverse('home'))
        calendar_hub = response.context['primary_zone']['calendar_hub']

        self.assertFalse(calendar_hub['record_board_enabled'])
        self.assertEqual(calendar_hub['continue_items'], [])
        self.assertNotContains(response, '교무수첩')

    @override_settings(SHEETBOOK_ENABLED=True, SHEETBOOK_DISCOVERY_VISIBLE=True)
    def test_v3_calendar_hub_reuses_record_board_data_without_public_sheetbook_copy(self):
        from sheetbook.models import Sheetbook

        user = self._login('v3sheetbookon')
        Sheetbook.objects.create(owner=user, title='운영 기록 보드', academic_year=2026)

        response = self.client.get(reverse('home'))
        calendar_hub = response.context['primary_zone']['calendar_hub']

        self.assertTrue(calendar_hub['record_board_enabled'])
        self.assertGreaterEqual(len(calendar_hub['continue_items']), 1)
        self.assertContains(response, '학급 캘린더 열기')
        self.assertNotContains(response, '교무수첩')
        self.assertNotContains(response, '학급 기록 보드에서 이어서 정리합니다.')
        descriptions = [item['description'] for item in calendar_hub['continue_items']]
        self.assertTrue(
            any(
                description in {'기록 작업을 바로 이어서 정리합니다.', '이전 작업 0개 흐름을 이어서 엽니다.'}
                or description.startswith('이전 작업 ')
                for description in descriptions
            )
        )

    def test_v3_calendar_summary_uses_summary_copy(self):
        self._login('v3calendar')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('Calendar Hub', content)
        self.assertIn('일정 빠른 추가', content)
        self.assertNotIn('개인 캘린더', content)
        self.assertNotIn('homeCalendarWidget()', content)
        self.assertNotIn('home-calendar-day', content)

    def test_v3_home_cards_expose_state_badges_and_standardized_cta_copy(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('로그인 필요', content)
        self.assertIn('공개 체험', content)
        self.assertIn('학생 참여', content)
        self.assertIn('시작하기', content)
        self.assertIn('가이드 보기', content)

    def test_v3_product_cards_attach_optional_guide_url_contract(self):
        manual = ServiceManual.objects.create(
            product=self.p1,
            title='수업 도구 시작하기',
            description='바로 쓰는 안내',
            is_published=True,
        )

        response = self.client.get(reverse('home'))
        popular_items = response.context['discovery_sections']['popular_items']
        guide_urls = [item['product'].guide_url for item in popular_items if item['product'].id == self.p1.id]

        self.assertIn(reverse('service_guide_detail', kwargs={'pk': manual.pk}), guide_urls)

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
