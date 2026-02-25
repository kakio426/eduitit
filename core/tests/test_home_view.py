from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from products.models import Product
from core.models import UserProfile, Post, Comment, ProductFavorite


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

    def _seed_sns_posts(self, count=6):
        author = _create_onboarded_user('snsauthor')
        for i in range(count):
            Post.objects.create(author=author, content=f'테스트 글 {i + 1}')
        return author

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

    def test_nav_uses_lg_breakpoint_to_prevent_mid_width_overflow(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('hidden lg:flex', content)
        self.assertIn('class="lg:hidden w-12 h-12', content)
        self.assertIn('class="fixed inset-x-0 z-40 lg:hidden', content)

    def test_mobile_widget_create_button_targets_mobile_container(self):
        _create_onboarded_user('mobilewidgetuser')
        self.client.login(username='mobilewidgetuser', password='pass1234')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('hx-post="/post/create/" hx-target="#mobile-post-list-container"', content)

    def test_pagination_buttons_render_per_widget_target(self):
        self._seed_sns_posts(count=6)
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('?page=2&target=post-list-container', content)
        self.assertIn('?page=2&target=mobile-post-list-container', content)
        self.assertIn('hx-target="#post-list-container"', content)
        self.assertIn('hx-target="#mobile-post-list-container"', content)

    def test_home_htmx_pagination_uses_mobile_target_from_header(self):
        self._seed_sns_posts(count=6)
        response = self.client.get(
            reverse('home'),
            {'page': 2},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='mobile-post-list-container',
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('hx-target="#mobile-post-list-container"', content)
        self.assertIn('?page=1&target=mobile-post-list-container', content)

    def test_home_htmx_pagination_invalid_target_falls_back_to_desktop(self):
        self._seed_sns_posts(count=6)
        response = self.client.get(
            reverse('home'),
            {'page': 2},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='invalid-container',
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('hx-target="#post-list-container"', content)
        self.assertIn('?page=1&target=post-list-container', content)

    def test_post_create_htmx_uses_mobile_target_from_header(self):
        self._seed_sns_posts(count=6)
        _create_onboarded_user('mobilewriter')
        self.client.login(username='mobilewriter', password='pass1234')
        response = self.client.post(
            reverse('post_create'),
            {'content': '모바일 새 글'},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='mobile-post-list-container',
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('hx-target="#mobile-post-list-container"', content)
        self.assertIn('?page=2&target=mobile-post-list-container', content)

    def test_sns_post_comment_buttons_use_local_htmx_targets(self):
        user = _create_onboarded_user('snsbtnuser')
        post = Post.objects.create(author=user, content='버튼 점검용 게시글')
        Comment.objects.create(post=post, author=user, content='버튼 점검용 댓글')
        self.client.login(username='snsbtnuser', password='pass1234')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('hx-target="closest [data-post-root]"', content)
        self.assertIn('hx-target="closest [data-comment-root]"', content)


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
        self.assertIn('교실 활동', content)
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
        """V2 로그인 홈 상단은 큰 인사말 대신 압축된 검색 행을 사용"""
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

    def test_v2_cards_use_direct_launch_with_separate_info_trigger(self):
        """V2 카드는 직접 진입 메타데이터 + 별도 상세 버튼을 함께 렌더링"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-launch-href="', content)
        self.assertIn('class="product-info-trigger', content)

    def test_v2_game_banner_has_separate_info_trigger(self):
        """게임 배너도 직접 진입 링크와 별도 상세 버튼을 제공"""
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-track="game_banner"', content)
        self.assertIn(f'aria-label="{self.p3.title} 상세 설명 열기"', content)

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

    def test_v2_authenticated_search_row_is_wrap_safe(self):
        self._login('searchlayout')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('mb-4 flex justify-end', content)
        self.assertIn('class="flex-shrink-0 flex items-center gap-2 bg-white rounded-xl', content)

    def test_v2_search_products_json_in_context(self):
        """V2 홈에 search_products_json 컨텍스트 존재"""
        response = self.client.get(reverse('home'))
        self.assertIn('search_products_json', response.context)

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

    def test_v2_quick_actions_prioritize_favorites(self):
        """즐겨찾기가 사용기록보다 먼저 퀵 액션에 노출된다."""
        from core.models import ProductUsageLog
        user = self._login('favoritepriority')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)
        for _ in range(3):
            ProductUsageLog.objects.create(user=user, product=self.p2, action='launch', source='home_quick')

        response = self.client.get(reverse('home'))
        quick_actions = response.context.get('quick_actions', [])
        self.assertGreaterEqual(len(quick_actions), 1)
        self.assertEqual(quick_actions[0]['product'].id, self.p1.id)

    def test_v2_context_contains_favorites(self):
        user = self._login('favoritecontext')
        ProductFavorite.objects.create(user=user, product=self.p2, pin_order=1)

        response = self.client.get(reverse('home'))
        favorite_items = response.context.get('favorite_items', [])
        favorite_product_ids = response.context.get('favorite_product_ids', [])

        self.assertEqual(len(favorite_items), 1)
        self.assertEqual(favorite_items[0]['product'].id, self.p2.id)
        self.assertIn(self.p2.id, favorite_product_ids)

    def test_v2_authenticated_renders_favorite_toggle_and_quick_slot(self):
        user = self._login('favoriteui')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-favorite-toggle="true"', content)
        self.assertIn('즐겨찾기', content)
        self.assertIn('home-favorite-ids-data', content)


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
        self.assertTrue(class_ops['has_more'])
        self.assertGreaterEqual(class_ops['remaining_count'], 1)

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

    def test_v2_anonymous_layout_has_sidebar_gap_and_shrink_safe_main(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('xl:flex-row xl:gap-6', content)
        self.assertIn('flex-1 min-w-0 pb-8', content)
        self.assertIn('xl:w-[340px] 2xl:w-[380px]', content)
        self.assertNotIn('overflow-hidden ml-6', content)

    def test_v2_authenticated_layout_has_sidebar_gap_and_shrink_safe_main(self):
        self._login('layoutauth')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('xl:flex-row xl:gap-6', content)
        self.assertIn('flex-1 min-w-0 p-4', content)
        self.assertIn('xl:w-[340px] 2xl:w-[380px]', content)


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


@override_settings(HOME_V2_ENABLED=True)
class ProductFavoriteAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.product = Product.objects.create(
            title="즐겨찾기 테스트",
            description="설명",
            price=0,
            is_active=True,
            service_type='classroom',
        )

    def _login(self, username='favoriteapiuser'):
        user = _create_onboarded_user(username)
        self.client.login(username=username, password='pass1234')
        return user

    def test_toggle_favorite_requires_login(self):
        import json
        response = self.client.post(
            reverse('toggle_product_favorite'),
            data=json.dumps({'product_id': self.product.id}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_toggle_favorite_add_and_remove(self):
        import json
        user = self._login('favoriteapiadd')

        add_response = self.client.post(
            reverse('toggle_product_favorite'),
            data=json.dumps({'product_id': self.product.id}),
            content_type='application/json',
        )
        self.assertEqual(add_response.status_code, 200)
        self.assertTrue(add_response.json()['is_favorite'])
        self.assertEqual(ProductFavorite.objects.filter(user=user, product=self.product).count(), 1)

        remove_response = self.client.post(
            reverse('toggle_product_favorite'),
            data=json.dumps({'product_id': self.product.id}),
            content_type='application/json',
        )
        self.assertEqual(remove_response.status_code, 200)
        self.assertFalse(remove_response.json()['is_favorite'])
        self.assertEqual(ProductFavorite.objects.filter(user=user, product=self.product).count(), 0)

    def test_favorites_list_returns_ordered_items(self):
        user = self._login('favoriteapilist')
        second = Product.objects.create(
            title="즐겨찾기 둘째",
            description="설명",
            price=0,
            is_active=True,
            service_type='work',
        )
        ProductFavorite.objects.create(user=user, product=second, pin_order=2)
        ProductFavorite.objects.create(user=user, product=self.product, pin_order=1)

        response = self.client.get(reverse('list_product_favorites'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['favorites'][0]['product_id'], self.product.id)
        self.assertEqual(payload['favorites'][1]['product_id'], second.id)
