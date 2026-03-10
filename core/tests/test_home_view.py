from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from products.models import Product
from core.models import UserProfile, Post, Comment, ProductFavorite, ProductWorkbenchBundle


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

    def _seed_notice_posts(self, count=6):
        author = _create_onboarded_user('noticeauthor')
        for i in range(count):
            Post.objects.create(
                author=author,
                content=f'공지 글 {i + 1}',
                post_type='news_link',
                approval_status='approved',
            )
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

    def test_sns_notice_inbox_button_renders(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('공지', content)
        self.assertIn('?feed_scope=notice&target=post-list-container', content)

    def test_staff_sns_operational_menu_includes_insight_queue_button(self):
        staff_user = _create_onboarded_user('staffopsmenu')
        staff_user.is_staff = True
        staff_user.save(update_fields=['is_staff'])
        self.client.login(username='staffopsmenu', password='pass1234')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn(reverse('news_review_queue'), content)
        self.assertIn(reverse('insight_sns_queue'), content)
        self.assertIn('인사이트 노출', content)

    def test_home_htmx_notice_feed_filters_to_notice_posts_only(self):
        author = _create_onboarded_user('noticefeedauthor')
        Post.objects.create(author=author, content='일반 글', post_type='general', approval_status='approved')
        Post.objects.create(author=author, content='공지 글', post_type='news_link', approval_status='approved')
        Post.objects.create(author=author, content='운영 공지 글', post_type='notice', approval_status='approved')
        Post.objects.create(author=author, content='보류 공지', post_type='news_link', approval_status='pending')
        Post.objects.create(author=author, content='보류 운영 공지', post_type='notice', approval_status='pending')

        response = self.client.get(
            reverse('home'),
            {'feed_scope': 'notice', 'target': 'post-list-container'},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='post-list-container',
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('data-feed-scope="notice"', content)
        self.assertIn('공지 글', content)
        self.assertIn('운영 공지 글', content)
        self.assertNotIn('일반 글', content)
        self.assertNotIn('보류 공지', content)
        self.assertNotIn('보류 운영 공지', content)

    def test_home_htmx_notice_feed_pagination_keeps_scope(self):
        self._seed_notice_posts(count=6)
        response = self.client.get(
            reverse('home'),
            {'feed_scope': 'notice', 'page': 2, 'target': 'post-list-container'},
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='post-list-container',
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('feed_scope=notice', content)
        self.assertIn('hx-target="#post-list-container"', content)

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

    def test_post_create_staff_notice_is_saved_as_notice(self):
        staff_user = _create_onboarded_user('staffnoticewriter')
        staff_user.is_staff = True
        staff_user.save(update_fields=['is_staff'])
        self.client.login(username='staffnoticewriter', password='pass1234')

        response = self.client.post(
            reverse('post_create'),
            {'content': '운영 공지 테스트', 'submit_kind': 'notice'},
        )

        self.assertEqual(response.status_code, 302)
        created_post = Post.objects.filter(author=staff_user).latest('created_at')
        self.assertEqual(created_post.post_type, 'notice')
        self.assertEqual(created_post.content, '운영 공지 테스트')

    def test_post_create_non_staff_notice_falls_back_to_general(self):
        normal_user = _create_onboarded_user('normalnoticewriter')
        self.client.login(username='normalnoticewriter', password='pass1234')

        response = self.client.post(
            reverse('post_create'),
            {'content': '일반 작성 테스트', 'submit_kind': 'notice'},
        )

        self.assertEqual(response.status_code, 302)
        created_post = Post.objects.filter(author=normal_user).latest('created_at')
        self.assertEqual(created_post.post_type, 'general')
        self.assertEqual(created_post.content, '일반 작성 테스트')

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
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_v2_anonymous_has_sections(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('수합·서명', content)
        self.assertIn('문서·작성', content)

    def test_v2_anonymous_has_login_cta(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('로그인하고 시작하기', content)

    def test_v2_anonymous_has_game_banner(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('교실 활동', content)
        self.assertIn('테스트 게임', content)
        self.assertNotIn('학생용 QR', content)

    def test_v2_authenticated_200(self):
        self._login('authuser')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_v2_authenticated_uses_compact_top_row_without_large_greeting(self):
        self._login('greetuser', nickname='홍길동')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertNotIn('선생님, 안녕하세요', content)
        self.assertIn('openSearchModal', content)
        self.assertIn('전체 서비스', content)
        self.assertIn('이용방법', content)
        self.assertIn('https://padlet.com/kakio1q2w/eduitit-wrjbzmk8oufxdzcv', content)

    def test_v2_authenticated_surfaces_sns_and_calendar_summary_cards(self):
        self._login('surfaceuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('SNS', content)
        self.assertIn('오늘 일정', content)
        self.assertIn('더 많은 도구', content)

    def test_v2_authenticated_has_quick_actions(self):
        self._login('qauser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-track="quick_action"', content)
        self.assertIn('내 작업대', content)
        self.assertIn('자주 쓰는 도구', content)

    def test_v2_authenticated_has_sections(self):
        self._login('secuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('수합·서명', content)
        self.assertIn('문서·작성', content)
        self.assertIn('핵심 업무', content)

    def test_v2_authenticated_has_discovery_and_calendar_preview(self):
        self._login('discoveruser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('새로 써보기', content)
        self.assertIn('오늘 일정', content)
        self.assertIn('달력 열기', content)

    def test_v2_authenticated_surfaces_student_games_entry_in_classroom_games(self):
        self._login('studentgameshome')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('학생용 게임 입장', content)
        self.assertIn('학생 링크 복사', content)
        self.assertIn('학생 화면 미리보기', content)

    def test_v2_mini_card_has_data_product_id(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn(f'data-product-id="{self.p1.id}"', content)

    def test_v2_mini_card_shows_solve_text(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('수업을 준비해요', content)

    def test_v2_workbench_cards_prefer_service_name_as_title(self):
        user = self._login('taskfirsthome')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        favorite_product = response.context['favorite_items'][0]['product']

        self.assertEqual(favorite_product.workbench_title, '수업 도구')
        self.assertEqual(favorite_product.workbench_summary, '수업을 준비해요')
        self.assertIn('수업 도구', content)
        self.assertIn('수업을 준비해요', content)

    def test_v2_home_strips_leading_emoji_from_teacher_first_labels(self):
        user = self._login('emojiworkbench')
        self.p1.title = '📒 수업 도구'
        self.p1.solve_text = '📒 수업을 준비해요'
        self.p1.icon = '📒'
        self.p1.save(update_fields=['title', 'solve_text', 'icon'])
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        favorite_items = response.context.get('favorite_items', [])
        favorite_product = next(item['product'] for item in favorite_items if item['product'].id == self.p1.id)

        self.assertEqual(favorite_product.teacher_first_task_label, '수업을 준비해요')
        self.assertEqual(favorite_product.teacher_first_service_label, '수업 도구')
        self.assertIn('수업을 준비해요', content)
        self.assertIn("'즐겨찾기 해제'", content)
        self.assertNotIn('📒 수업을 준비해요', content)
        self.assertNotIn('利먭꺼李얘린', content)

    def test_v2_cards_use_direct_launch_with_separate_info_trigger(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-launch-href="', content)
        self.assertIn('class="product-info-trigger', content)

    def test_v2_context_sections_count(self):
        response = self.client.get(reverse('home'))
        sections = response.context.get('sections', [])
        self.assertGreaterEqual(len(sections), 2)

    def test_v2_context_quick_actions_max_5(self):
        self._login('maxuser')
        response = self.client.get(reverse('home'))
        quick_actions = response.context.get('quick_actions', [])
        self.assertLessEqual(len(quick_actions), 5)
        self.assertGreaterEqual(len(quick_actions), 1)

    def test_v2_has_search_button(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('openSearchModal', content)

    def test_v2_search_products_json_in_context(self):
        response = self.client.get(reverse('home'))
        self.assertIn('search_products_json', response.context)

    def test_v2_context_contains_home_summary_context(self):
        self._login('summarycontextuser')
        response = self.client.get(reverse('home'))
        self.assertIn('home_calendar_summary', response.context)
        self.assertIn('home_sns_summary', response.context)
        self.assertIn('workbench_primary_items', response.context)
        self.assertIn('workbench_recent_items', response.context)

    def test_v2_usage_based_quick_actions(self):
        from core.models import ProductUsageLog
        user = self._login('usageuser')
        for _ in range(5):
            ProductUsageLog.objects.create(user=user, product=self.p2, action='launch', source='home_quick')
        response = self.client.get(reverse('home'))
        quick_actions = response.context.get('quick_actions', [])
        self.assertEqual(quick_actions[0]['product'].id, self.p2.id)

    def test_v2_quick_actions_prioritize_favorites(self):
        from core.models import ProductUsageLog
        user = self._login('favoritepriority')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)
        for _ in range(3):
            ProductUsageLog.objects.create(user=user, product=self.p2, action='launch', source='home_quick')

        response = self.client.get(reverse('home'))
        quick_actions = response.context.get('quick_actions', [])
        self.assertGreaterEqual(len(quick_actions), 1)
        self.assertEqual(quick_actions[0]['product'].id, self.p1.id)

    def test_v2_context_contains_recent_items_separate_from_workbench(self):
        from core.models import ProductUsageLog

        user = self._login('recentitemsuser')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)
        ProductUsageLog.objects.create(user=user, product=self.p2, action='launch', source='home_quick')
        ProductUsageLog.objects.create(user=user, product=self.p3, action='launch', source='home_section')

        response = self.client.get(reverse('home'))
        recent_items = response.context.get('recent_items', [])

        self.assertEqual([item['product'].id for item in recent_items], [self.p3.id, self.p2.id])
        self.assertNotIn(self.p1.id, [item['product'].id for item in recent_items])

    def test_v2_context_contains_favorites(self):
        user = self._login('favoritecontext')
        ProductFavorite.objects.create(user=user, product=self.p2, pin_order=1)

        response = self.client.get(reverse('home'))
        favorite_items = response.context.get('favorite_items', [])
        favorite_product_ids = response.context.get('favorite_product_ids', [])

        self.assertEqual(len(favorite_items), 1)
        self.assertEqual(favorite_items[0]['product'].id, self.p2.id)
        self.assertIn(self.p2.id, favorite_product_ids)

    def test_v2_authenticated_surfaces_add_to_workbench_copy_on_discovery(self):
        self._login('workbenchcopy')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('작업대에 추가', content)

    def test_v2_authenticated_renders_recent_items_section_when_usage_exists(self):
        from core.models import ProductUsageLog

        user = self._login('recentsectionuser')
        ProductUsageLog.objects.create(user=user, product=self.p2, action='launch', source='home_quick')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('최근 이어서', content)
        self.assertNotIn('<h2 class="text-lg font-black text-slate-900">최근 이어서</h2>', content)

    def test_v2_context_contains_companion_items_for_teacher_flow(self):
        user = self._login('companioncontextuser')
        collect_tool = Product.objects.create(
            title="동의서 도구",
            description="동의서 작성",
            price=0,
            is_active=True,
            service_type='collect_sign',
        )
        ProductFavorite.objects.create(user=user, product=self.p2, pin_order=1)

        response = self.client.get(reverse('home'))
        companion_items = response.context.get('companion_items', [])

        self.assertGreaterEqual(len(companion_items), 1)
        self.assertEqual(companion_items[0]['product'].id, collect_tool.id)
        self.assertEqual(companion_items[0]['reason_label'], '문서·작성과 같이 쓰기')

    def test_v2_authenticated_renders_companion_recommendations_section(self):
        user = self._login('companionrenderuser')
        Product.objects.create(
            title="동의서 도구",
            description="동의서 작성",
            price=0,
            is_active=True,
            service_type='collect_sign',
        )
        ProductFavorite.objects.create(user=user, product=self.p2, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('같이 쓰면 좋은 도구', content)
        self.assertIn('문서·작성과 같이 쓰기', content)
        self.assertIn('data-track="companion_card"', content)

    def test_v2_discovery_fallback_keeps_add_to_workbench_cta_when_quick_actions_exhaust_pool(self):
        from core.models import ProductUsageLog

        user = self._login('discoveryfallbackuser')
        p4 = Product.objects.create(
            title="동의서 도구", description="동의서 작성", price=0,
            is_active=True, service_type='collect_sign',
        )
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)
        ProductFavorite.objects.create(user=user, product=self.p2, pin_order=2)
        ProductUsageLog.objects.create(user=user, product=self.p3, action='launch', source='home_quick')
        ProductUsageLog.objects.create(user=user, product=p4, action='launch', source='home_quick')

        response = self.client.get(reverse('home'))
        discovery_items = response.context.get('discovery_items', [])
        content = response.content.decode('utf-8')

        self.assertGreaterEqual(len(discovery_items), 1)
        self.assertIn('새로 써보기', content)
        self.assertIn('작업대에 추가', content)

    def test_v2_authenticated_renders_empty_workbench_slots_when_not_full(self):
        user = self._login('workbenchslotsuser')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('빈 자리 2', content)
        self.assertIn('기본 슬롯', content)

    def test_v2_authenticated_renders_weekly_bundle_highlights(self):
        user = self._login('weeklybundleuser')
        ProductWorkbenchBundle.objects.create(
            user=user,
            name='이번 주 학급 운영',
            product_ids=[self.p1.id, self.p2.id],
            last_used_at=timezone.now(),
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('이번 주 많이 쓰는 조합', content)
        self.assertIn('이번 주 학급 운영', content)
        self.assertIn('수업을 준비해요 + 행정 도구', content)

    def test_v2_context_weekly_bundle_items_are_capped(self):
        from datetime import timedelta

        user = self._login('weeklybundlecapuser')
        for idx in range(3):
            ProductWorkbenchBundle.objects.create(
                user=user,
                name=f'조합 {idx + 1}',
                product_ids=[self.p1.id, self.p2.id],
                last_used_at=timezone.now() - timedelta(minutes=idx),
            )

        response = self.client.get(reverse('home'))
        weekly_bundle_items = response.context.get('weekly_bundle_items', [])

        self.assertLessEqual(len(weekly_bundle_items), 2)

    def test_v2_recommendation_sections_render_after_workbench(self):
        user = self._login('sectionorderuser')
        ProductFavorite.objects.create(user=user, product=self.p2, pin_order=1)
        Product.objects.create(
            title="동의서 도구",
            description="동의서 작성",
            price=0,
            is_active=True,
            service_type='collect_sign',
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertLess(content.index('내 작업대'), content.index('같이 쓰면 좋은 도구'))

    def test_v2_authenticated_renders_saved_workbench_bundle(self):
        user = self._login('bundlehomeuser')
        ProductWorkbenchBundle.objects.create(user=user, name='학급 운영 세트', product_ids=[self.p1.id, self.p2.id])

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('저장한 조합', content)
        self.assertIn('학급 운영 세트', content)
        self.assertIn('수업을 준비해요 · 행정 도구', content)
        self.assertIn('이 조합 불러오기', content)
        self.assertIn('조합 지우기', content)
        self.assertIn('data-workbench-bundle-apply="true"', content)
        self.assertIn('data-workbench-bundle-delete="true"', content)
        self.assertNotIn('이 조합 저장', content)

    def test_v2_authenticated_renders_workbench_accessibility_contract(self):
        user = self._login('workbencha11yuser')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('id="workbenchKeyboardHint"', content)
        self.assertIn('data-workbench-live="true"', content)
        self.assertIn('aria-live="polite"', content)
        self.assertIn('aria-describedby="workbenchKeyboardHint"', content)

    def test_v2_authenticated_renders_responsive_workbench_controls(self):
        user = self._login('workbenchmobilecontrols')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-mobile-label="위로 이동"', content)
        self.assertIn('data-mobile-label="아래로 이동"', content)
        self.assertIn('data-desktop-label="왼쪽으로 이동"', content)
        self.assertIn('data-desktop-label="오른쪽으로 이동"', content)
        self.assertIn('>위</span>', content)
        self.assertIn('>아래</span>', content)
        self.assertIn('>왼쪽</span>', content)
        self.assertIn('>오른쪽</span>', content)

    def test_v2_workbench_cards_use_compact_height_contract(self):
        from core.models import ProductUsageLog

        user = self._login('workbenchdensity')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)
        ProductUsageLog.objects.create(user=user, product=self.p2, action='launch', source='home_quick')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('min-h-[110px]', content)
        self.assertNotIn('min-h-[132px]', content)
        self.assertIn('min-h-[84px]', content)


    def test_v2_home_sns_panel_restores_feed_preview_and_notice_contract(self):
        self._login('homesnsfeed')
        author = _create_onboarded_user('homesnsauthor', nickname='담임쌤')
        Post.objects.create(
            author=author,
            content='사진이 있는 SNS 글입니다.',
            post_type='news_link',
            approval_status='approved',
            og_title='학교 공지 미리보기',
            og_description='사진과 함께 보는 SNS 미리보기입니다.',
            og_image_url='https://example.com/sample.jpg',
            source_url='https://example.com/news-link',
        )
        Post.objects.create(
            author=author,
            content='운영 공지입니다.',
            post_type='notice',
            approval_status='approved',
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        sns_summary = response.context['home_sns_summary']
        previews = {item['post_type']: item for item in sns_summary['latest_posts']}

        self.assertIn('SNS', content)
        self.assertNotIn('SNS 더 보기', content)
        self.assertIn('data-sns-preview-link="true"', content)
        self.assertIn('SNS 전체 보기', content)
        self.assertEqual(sns_summary['notice_count'], 1)
        self.assertEqual(previews['news_link']['author_display'], '담임쌤')
        self.assertEqual(previews['news_link']['thumbnail'], 'https://example.com/sample.jpg')
        self.assertEqual(previews['news_link']['badge_label'], '링크')
        self.assertEqual(previews['news_link']['detail_href'], 'https://example.com/news-link')
        self.assertTrue(previews['news_link']['detail_external'])
        self.assertEqual(previews['notice']['badge_label'], '공지')
        self.assertFalse(previews['notice']['detail_external'])
        self.assertIn('사진과 함께 보는 SNS 미리보기입니다.', content)
        self.assertNotIn('공지 2건', content)


    def test_v2_authenticated_renders_favorite_toggle_and_quick_slot(self):
        user = self._login('favoriteui')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-favorite-toggle="true"', content)
        self.assertIn('home-favorite-ids-data', content)
        self.assertIn('작업대 정리', content)

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

    def test_v2_handoff_route_maps_to_collect_sign_section(self):
        handoff_product = Product.objects.create(
            title="배부 체크",
            description="배부 체크 서비스",
            price=0,
            is_active=True,
            service_type='work',
            launch_route_name='handoff:landing',
        )

        response = self.client.get(reverse('home'))
        sections = response.context.get('sections', [])
        collect_sign = next((section for section in sections if section.get('key') == 'collect_sign'), None)

        self.assertIsNotNone(collect_sign)
        collect_ids = [product.id for product in collect_sign['products']]
        self.assertIn(handoff_product.id, collect_ids)

    def test_v2_collect_sign_service_type_falls_back_to_collect_sign_section(self):
        collect_product = Product.objects.create(
            title="수합 전용 도구",
            description="수합·서명 섹션 테스트",
            price=0,
            is_active=True,
            service_type='collect_sign',
            launch_route_name='',
        )

        response = self.client.get(reverse('home'))
        sections = response.context.get('sections', [])
        collect_sign = next((section for section in sections if section.get('key') == 'collect_sign'), None)

        self.assertIsNotNone(collect_sign)
        collect_ids = [product.id for product in collect_sign['products']]
        self.assertIn(collect_product.id, collect_ids)

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
        Product.objects.create(
            title="Classroom Extra 3",
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
        Product.objects.create(
            title="Classroom Extra 3",
            description="extra",
            price=0,
            is_active=True,
            service_type='classroom',
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-track="section_more_toggle"', content)
        self.assertIn('더보기', content)

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_v2_authenticated_sheetbook_workspace_blocks_render(self):
        from sheetbook.models import Sheetbook

        user = self._login('sheetbookhome')
        Sheetbook.objects.create(owner=user, title='2026 2-3반 교무수첩')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('내 작업대', content)
        self.assertNotIn('오늘 바로 시작', content)

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_v2_authenticated_sheetbook_workspace_prefers_calendar_summary_over_workspace_cta(self):
        self._login('sheetbookcta')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('오늘 일정', content)
        self.assertIn('달력 열기', content)
        self.assertNotIn('workspace_home_create', content)

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_v2_authenticated_sheetbook_workspace_shows_first_run_onboarding(self):
        self._login('sheetbookonboarding')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('내 작업대', content)
        self.assertNotIn('바로 시작 순서', content)

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_v2_authenticated_sheetbook_workspace_prefers_favorites_heading(self):
        from sheetbook.models import Sheetbook

        user = self._login('sheetbookfavorite')
        ProductFavorite.objects.create(user=user, product=self.p2, pin_order=1)
        Sheetbook.objects.create(owner=user, title='즐겨찾기 테스트 수첩')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('내 작업대', content)
        self.assertIn('작업대 정리', content)

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_v2_authenticated_sheetbook_today_rows_render(self):
        from sheetbook.models import Sheetbook, SheetTab, SheetColumn, SheetRow, SheetCell

        user = self._login('sheetbooktoday')
        sheetbook = Sheetbook.objects.create(owner=user, title='오늘 테스트 수첩')
        tab = SheetTab.objects.create(
            sheetbook=sheetbook,
            name='일정',
            tab_type=SheetTab.TYPE_GRID,
            sort_order=1,
        )
        col_date = SheetColumn.objects.create(
            tab=tab,
            key='date',
            label='날짜',
            column_type=SheetColumn.TYPE_DATE,
            sort_order=1,
        )
        col_title = SheetColumn.objects.create(
            tab=tab,
            key='title',
            label='제목',
            column_type=SheetColumn.TYPE_TEXT,
            sort_order=2,
        )
        row = SheetRow.objects.create(tab=tab, sort_order=1, created_by=user, updated_by=user)
        SheetCell.objects.create(row=row, column=col_date, value_date=timezone.localdate())
        SheetCell.objects.create(row=row, column=col_title, value_text='외부강사 수업')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('외부강사 수업', content)
        self.assertIn('오늘 테스트 수첩', content)

    @override_settings(SHEETBOOK_ENABLED=True)
    def test_v2_authenticated_sheetbook_workspace_event_logged(self):
        from sheetbook.models import SheetbookMetricEvent

        user = self._login('sheetbookhomeevent')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            SheetbookMetricEvent.objects.filter(
                event_name='workspace_home_opened',
                user=user,
            ).exists()
        )


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

    def test_save_workbench_bundle_creates_and_updates(self):
        import json
        user = self._login('bundleapisave')
        second = Product.objects.create(
            title="작업대 둘째",
            description="설명",
            price=0,
            is_active=True,
            service_type='work',
        )
        ProductFavorite.objects.create(user=user, product=self.product, pin_order=1)
        ProductFavorite.objects.create(user=user, product=second, pin_order=2)

        create_response = self.client.post(
            reverse('save_workbench_bundle'),
            data=json.dumps({'name': '행정 시작 세트', 'product_ids': [self.product.id, second.id]}),
            content_type='application/json',
        )
        self.assertEqual(create_response.status_code, 200)
        payload = create_response.json()
        self.assertEqual(payload['status'], 'ok')
        self.assertTrue(payload['created'])
        bundle = ProductWorkbenchBundle.objects.get(user=user, name='행정 시작 세트')
        self.assertEqual(bundle.product_ids, [self.product.id, second.id])

        update_response = self.client.post(
            reverse('save_workbench_bundle'),
            data=json.dumps({'name': '행정 시작 세트', 'product_ids': [second.id]}),
            content_type='application/json',
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertFalse(update_response.json()['created'])
        bundle.refresh_from_db()
        self.assertEqual(bundle.product_ids, [second.id])

    def test_list_workbench_bundles_returns_saved_items(self):
        user = self._login('bundleapilist')
        ProductWorkbenchBundle.objects.create(user=user, name='첫 조합', product_ids=[self.product.id])
        ProductWorkbenchBundle.objects.create(user=user, name='둘째 조합', product_ids=[self.product.id])

        response = self.client.get(reverse('list_workbench_bundles'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(len(payload['bundles']), 2)
        self.assertEqual(payload['bundles'][0]['name'], '둘째 조합')

    def test_apply_workbench_bundle_reorders_and_creates_missing_favorites(self):
        import json
        user = self._login('bundleapplyuser')
        second = Product.objects.create(
            title="작업대 적용 둘째",
            description="설명",
            price=0,
            is_active=True,
            service_type='work',
        )
        third = Product.objects.create(
            title="작업대 적용 셋째",
            description="설명",
            price=0,
            is_active=True,
            service_type='game',
        )
        ProductFavorite.objects.create(user=user, product=self.product, pin_order=1)
        ProductFavorite.objects.create(user=user, product=second, pin_order=2)
        bundle = ProductWorkbenchBundle.objects.create(user=user, name='학급 운영 세트', product_ids=[third.id, self.product.id])

        response = self.client.post(reverse('apply_workbench_bundle', args=[bundle.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['bundle_name'], '학급 운영 세트')

        favorites = list(ProductFavorite.objects.filter(user=user).order_by('pin_order'))
        self.assertEqual([favorite.product_id for favorite in favorites], [third.id, self.product.id, second.id])
        bundle.refresh_from_db()
        self.assertIsNotNone(bundle.last_used_at)

    def test_delete_workbench_bundle_removes_saved_bundle(self):
        user = self._login('bundledeleteuser')
        bundle = ProductWorkbenchBundle.objects.create(user=user, name='지울 조합', product_ids=[self.product.id])

        response = self.client.post(reverse('delete_workbench_bundle', args=[bundle.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['status'], 'ok')
        self.assertEqual(payload['bundle_name'], '지울 조합')
        self.assertFalse(ProductWorkbenchBundle.objects.filter(id=bundle.id).exists())

    def test_reorder_favorites_updates_pin_order(self):
        import json
        user = self._login('favoriteapireorder')
        second = Product.objects.create(
            title="즐겨찾기 둘째",
            description="설명",
            price=0,
            is_active=True,
            service_type='work',
        )
        ProductFavorite.objects.create(user=user, product=self.product, pin_order=1)
        ProductFavorite.objects.create(user=user, product=second, pin_order=2)

        response = self.client.post(
            reverse('reorder_product_favorites'),
            data=json.dumps({'product_ids': [second.id, self.product.id]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

        refreshed = list(ProductFavorite.objects.filter(user=user).order_by('pin_order'))
        self.assertEqual(refreshed[0].product_id, second.id)
        self.assertEqual(refreshed[1].product_id, self.product.id)
