import json
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from classcalendar.models import CalendarCollaborator, CalendarEvent, CalendarTask, EventPageBlock
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
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from core.views import _build_home_v4_representative_slots, _rotate_items
from products.models import Product
from core.models import Post, ProductFavorite, ProductUsageLog, UserPolicyConsent, UserProfile


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

    def _create_sheetbook_product(self, title='숨김 교무수첩', *, is_active=True):
        return Product.objects.create(
            title=title,
            description='표 작업',
            price=0,
            is_active=is_active,
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

    def test_v1_home_hides_inactive_sheetbook_product(self):
        self._create_sheetbook_product(is_active=False)

        response = self.client.get(reverse('home'))
        product_titles = [product.title for product in response.context['products']]

        self.assertNotIn('숨김 교무수첩', product_titles)
        self.assertNotContains(response, '숨김 교무수첩')

    def test_v1_service_launcher_json_hides_inactive_sheetbook(self):
        self._create_sheetbook_product(is_active=False)

        response = self.client.get(reverse('home'))
        payload = json.loads(response.context['service_launcher_json'])
        titles = [item['title'] for item in payload]

        self.assertNotIn('학급 기록 보드', titles)

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

    def _create_sheetbook_product(self, title='숨김 교무수첩', *, is_active=True):
        return Product.objects.create(
            title=title,
            description='표 작업',
            price=0,
            is_active=is_active,
            service_type='classroom',
            launch_route_name='sheetbook:index',
        )

    def _create_try_now_products(self):
        notice = Product.objects.create(
            title="알림장 & 주간학습 멘트 생성기",
            description="안내문 작성",
            price=0,
            is_active=True,
            service_type='work',
            launch_route_name='noticegen:main',
            icon='fa-solid fa-note-sticky',
        )
        collect = Product.objects.create(
            title="간편 수합",
            description="제출 수합",
            price=0,
            is_active=True,
            is_guest_allowed=True,
            service_type='collect_sign',
            launch_route_name='collect:landing',
            icon='fa-solid fa-inbox',
        )
        return notice, collect

    def _create_try_now_support_products(self):
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
        return qr, prompt

    def _create_calendar_event_with_note(self, user, *, title, note, start_time=None, end_time=None):
        start_time = start_time or timezone.now().replace(second=0, microsecond=0)
        end_time = end_time or (start_time + timedelta(hours=1))
        event = CalendarEvent.objects.create(
            title=title,
            author=user,
            start_time=start_time,
            end_time=end_time,
            color='indigo',
            visibility=CalendarEvent.VISIBILITY_TEACHER,
        )
        EventPageBlock.objects.create(
            event=event,
            block_type='text',
            content={'text': note},
            order=0,
        )
        return event

    def _sorted_event_source(self, response):
        return sorted(response.context['events_json'], key=lambda item: item['id'])

    def _sorted_task_source(self, response):
        return sorted(response.context['tasks_json'], key=lambda item: item['id'])

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
        self.assertIn('지금 바로 써보기', content)
        self.assertIn('로그인 후 전체 열기', content)
        self.assertNotIn('공개 도구 먼저 보기', content)
        self.assertEqual(content.count('로그인 후 전체 열기'), 1)

    def test_v2_anonymous_surfaces_public_cards_before_locked_sections(self):
        public_collect = Product.objects.create(
            title="공개 수합",
            description="제출 흐름을 바로 볼 수 있어요",
            price=0,
            is_active=True,
            is_guest_allowed=True,
            service_type='collect_sign',
            icon='fa-solid fa-inbox',
        )
        public_qr = Product.objects.create(
            title="공개 QR",
            description="QR 미리보기",
            price=0,
            is_active=True,
            is_guest_allowed=True,
            service_type='classroom',
            icon='fa-solid fa-qrcode',
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-v2-public-section="true"', content)
        self.assertIn('지금 바로 써보기', content)
        self.assertIn('로그인 후 더 강력한 도구', content)
        self.assertIn('미리보기 가능', content)
        self.assertIn('로그인 필요', content)

        public_ids = [card['id'] for card in response.context.get('guest_public_cards', [])]
        self.assertIn(public_collect.id, public_ids)
        self.assertIn(public_qr.id, public_ids)

        locked_section_ids = []
        for section in response.context.get('guest_primary_display_sections', []):
            locked_section_ids.extend(product.id for product in section.get('products', []))
            locked_section_ids.extend(product.id for product in section.get('overflow_products', []))
        for section in response.context.get('guest_secondary_display_sections', []):
            locked_section_ids.extend(product.id for product in section.get('products', []))
            locked_section_ids.extend(product.id for product in section.get('overflow_products', []))

        self.assertIn(self.p1.id, locked_section_ids)
        self.assertIn(self.p2.id, locked_section_ids)
        self.assertNotIn(public_collect.id, locked_section_ids)
        self.assertNotIn(public_qr.id, locked_section_ids)

    def test_v2_anonymous_removes_hero_access_legend(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertNotIn('미리보기 가능 먼저 표시', content)
        self.assertNotIn('로그인 필요 미리 안내', content)
        self.assertNotIn('데모·가이드로 우회 가능', content)

    def test_v2_anonymous_cards_use_single_priority_badge(self):
        external_public = Product.objects.create(
            title="외부 공개 도구",
            description="새 창으로 바로 이동",
            price=0,
            is_active=True,
            is_guest_allowed=True,
            service_type='edutech',
            external_url='https://example.com/demo',
            icon='fa-solid fa-arrow-up-right-from-square',
        )
        Product.objects.create(
            title="파일 필요한 로그인 도구",
            description="로그인 후 파일 업로드",
            price=0,
            is_active=True,
            service_type='work',
            launch_route_name='noticegen:main',
            icon='fa-solid fa-file-arrow-up',
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        external_card = next(
            card for card in response.context.get('guest_public_cards', [])
            if card['id'] == external_public.id
        )
        self.assertEqual(external_card['access_status_label'], '외부 이동')
        self.assertIn('외부 이동', content)
        self.assertNotIn('text-slate-600">파일 필요</span>', content)
        self.assertNotIn('text-indigo-700">가이드 있음</span>', content)

    def test_v2_anonymous_prioritizes_hero_and_services_without_sns_preview(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        hero_index = content.index('data-home-v2-guest-hero="true"')
        service_group_index = content.index('id="guest-home-services"')

        self.assertLess(hero_index, service_group_index)
        self.assertNotIn('data-home-v2-public-calendar-entry="true"', content)
        self.assertNotIn('sns-full-section-v2', content)
        self.assertNotIn('실시간 소통', content)

    def test_v2_anonymous_does_not_render_today_try_now_section(self):
        self._create_try_now_products()
        self._create_try_now_support_products()

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertNotIn('data-home-v2-try-now="true"', content)
        self.assertNotIn('data-home-v2-try-now-grid="true"', content)

    def test_v2_anonymous_keeps_guest_home_without_mini_app_rail(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertNotIn('data-home-v2-mini-app-rail="true"', content)
        self.assertNotIn('data-home-mini-app-shell="true"', content)

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

    def test_v2_anonymous_does_not_render_authenticated_calendar_hub(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertNotIn('data-home-v2-top-calendar="true"', content)
        self.assertNotIn('오늘 실행판 열기', content)
        self.assertNotIn('학급 캘린더', content)

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
        """V2 로그인 홈은 캘린더 단일 표면을 상단 전체 폭으로 사용"""
        self._login('qauser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-home-v2-top-zone="true"', content)
        self.assertIn('data-home-calendar-root="true"', content)
        self.assertIn('data-home-v2-calendar-surface="true"', content)
        self.assertIn('data-classcalendar-surface="true"', content)
        self.assertIn('data-classcalendar-embed-mode="home"', content)
        self.assertIn('data-classcalendar-main-view="true"', content)
        self.assertIn('surfaceAllowsManage: true', content)
        self.assertIn('새 일정', content)
        self.assertNotIn('data-home-v2-top-today="true"', content)
        self.assertNotIn('data-home-v2-top-center="true"', content)
        self.assertNotIn('homeCalendarWidget()', content)
        self.assertNotIn('openTodayMemoModal($event)', content)
        self.assertNotIn('data-home-v2-calendar-month-grid="true"', content)
        self.assertNotIn('data-home-v2-calendar-day="true"', content)
        self.assertNotIn('안내문에서 일정 찾기', content)

    def test_v2_authenticated_does_not_render_today_try_now_section(self):
        self._create_try_now_products()
        self._create_try_now_support_products()
        self._login('trynowuser')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-v2-top-zone="true"', content)
        self.assertIn('data-home-v2-service-groups="true"', content)
        self.assertNotIn('data-home-v2-try-now="true"', content)
        self.assertNotIn('data-home-v2-try-now-grid="true"', content)
        self.assertNotIn('data-home-v2-try-now-support="true"', content)
        self.assertNotIn('data-home-v2-try-now-support-grid="true"', content)
        self.assertNotIn('오늘 바로 써보기', content)

    @override_settings(
        FEATURE_MESSAGE_CAPTURE_ENABLED=True,
        FEATURE_MESSAGE_CAPTURE_ITEM_TYPES=True,
    )
    def test_v2_authenticated_calendar_hub_shows_single_message_entry(self):
        self._login('capturehome')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-classcalendar-main-view="true"', content)
        self.assertIn('data-classcalendar-embed-mode="home"', content)
        self.assertNotIn('openTodayMemoModal($event)', content)
        self.assertNotIn('data-home-v2-today-memo-modal="true"', content)
        self.assertNotIn('openMessageHub($event, \'capture\', { resetCapture: true })', content)
        self.assertNotIn('안내문에서 일정 찾기', content)

    @override_settings(
        FEATURE_MESSAGE_CAPTURE_ENABLED=True,
        FEATURE_MESSAGE_CAPTURE_ITEM_TYPES=True,
    )
    def test_v2_home_shows_messagebox_card_without_service_grid_duplication(self):
        Product.objects.create(
            title="업무 메시지 보관함",
            description="메시지 보관",
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='messagebox:main',
        )
        self._login('capturecard')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-messagebox-card="true"', content)
        self.assertIn('업무 메시지 보관함', content)
        self.assertIn('data-home-messagebox-actions="true"', content)
        self.assertIn('메시지 보관', content)
        self.assertIn('href="/messagebox/#messagebox-compose"', content)
        self.assertIn('href="/messagebox/#messagebox-archive"', content)
        self.assertIn('data-classcalendar-main-view="true"', content)
        self.assertNotIn('놓치지 않을 메시지', content)
        self.assertNotIn('메신저에서 받은 중요한 내용을 붙여넣고, 나중에 다시 보거나 일정에 연결하세요.', content)
        self.assertLess(
            content.index('data-classcalendar-main-view="true"'),
            content.index('data-home-messagebox-card="true"'),
        )

        section_products = [
            product.launch_route_name
            for section in [*response.context['sections'], *response.context['aux_sections']]
            for product in section.get('products', [])
        ]
        self.assertNotIn('messagebox:main', section_products)

    def test_v2_authenticated_calendar_surface_keeps_note_source_in_shared_data(self):
        user = self._login('memouser')
        now = timezone.now().replace(second=0, microsecond=0)
        self._create_calendar_event_with_note(
            user,
            title='체험학습 안내',
            note='1교시 전에 QR 띄우기\n준비물 다시 확인',
            start_time=now - timedelta(minutes=15),
            end_time=now + timedelta(minutes=45),
        )
        self._create_calendar_event_with_note(
            user,
            title='공개수업 준비',
            note='마이크 배터리 확인\n학부모 동선 안내',
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        event_notes = {
            (item['title'], item['note'])
            for item in self._sorted_event_source(response)
        }

        self.assertIn('data-classcalendar-main-view="true"', content)
        self.assertIn(('체험학습 안내', '1교시 전에 QR 띄우기\n준비물 다시 확인'), event_notes)
        self.assertIn(('공개수업 준비', '마이크 배터리 확인\n학부모 동선 안내'), event_notes)
        self.assertNotIn('data-home-v2-calendar-today-memos="true"', content)
        self.assertNotIn('오늘의 메모 열기', content)
        self.assertNotIn('다시 볼 메모 열기', content)

    def test_v2_authenticated_calendar_surface_uses_shared_calendar_source(self):
        viewer = self._login('sharedviewer')
        owner = _create_onboarded_user('sharedowner')
        CalendarCollaborator.objects.create(
            owner=owner,
            collaborator=viewer,
            can_edit=False,
        )
        now = timezone.make_aware(datetime.combine(timezone.localdate(), time(hour=10)))
        self._create_calendar_event_with_note(
            owner,
            title='공유된 공개수업 준비',
            note='공유 달력 준비물도 홈에서 바로 보여야 함',
            start_time=now,
            end_time=now + timedelta(hours=1),
        )

        home_response = self.client.get(reverse('home'))
        main_response = self.client.get(reverse('calendar_main'), follow=True)
        home_events = self._sorted_event_source(home_response)
        main_events = self._sorted_event_source(main_response)

        self.assertIn(
            ('공유된 공개수업 준비', '공유 달력 준비물도 홈에서 바로 보여야 함'),
            {(item['title'], item['note']) for item in home_events},
        )
        self.assertEqual(home_events, main_events)
        self.assertEqual(self._sorted_task_source(home_response), self._sorted_task_source(main_response))
        self.assertEqual(home_response.context['initial_selected_date'], main_response.context['initial_selected_date'])
        self.assertEqual(home_response.context['calendar_page_variant'], 'main')
        self.assertEqual(main_response.context['calendar_page_variant'], 'main')

    def test_v2_authenticated_calendar_surface_does_not_render_supporting_sections(self):
        user = self._login('upcominguser')
        tomorrow = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=1), time(hour=9)))
        CalendarEvent.objects.create(
            title='내일 학부모총회',
            author=user,
            start_time=tomorrow,
            end_time=tomorrow + timedelta(hours=1),
            color='indigo',
            visibility=CalendarEvent.VISIBILITY_TEACHER,
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        event_titles = {item['title'] for item in self._sorted_event_source(response)}

        self.assertIn('data-classcalendar-main-view="true"', content)
        self.assertIn('내일 학부모총회', event_titles)
        self.assertNotIn('data-home-v2-calendar-empty="true"', content)
        self.assertNotIn('data-home-v2-calendar-supporting="true"', content)

    def test_v2_authenticated_calendar_surface_uses_selected_date_from_query(self):
        user = self._login('detailuser')
        now = timezone.make_aware(datetime.combine(timezone.localdate(), time(hour=11)))
        target_date = (timezone.localdate() + timedelta(days=2)).isoformat()
        self._create_calendar_event_with_note(
            user,
            title='상세 확인 일정',
            note='링크는 홈 캘린더 상세로 연결',
            start_time=now,
            end_time=now + timedelta(hours=1),
        )

        response = self.client.get(f"{reverse('home')}?date={target_date}")
        content = response.content.decode('utf-8')

        self.assertEqual(response.context['initial_selected_date'], target_date)
        self.assertIn('data-classcalendar-embed-mode="home"', content)

    def test_v2_authenticated_calendar_surface_defaults_to_nearest_upcoming_item_date(self):
        user = self._login('upcomingfocususer')
        today = timezone.localdate()
        future_event_date = today + timedelta(days=5)
        nearest_task_date = today + timedelta(days=2)
        event_start = timezone.make_aware(datetime.combine(future_event_date, time(hour=10)))
        task_due = timezone.make_aware(datetime.combine(nearest_task_date, time(hour=8)))
        self._create_calendar_event_with_note(
            user,
            title='다음 주 공개수업 준비',
            note='홈 첫 진입은 실제 저장 일정 날짜로 열려야 함',
            start_time=event_start,
            end_time=event_start + timedelta(hours=1),
        )
        CalendarTask.objects.create(
            author=user,
            title='가장 가까운 준비 할 일',
            note='오늘 공지 일정보다 먼저 보여야 함',
            due_at=task_due,
            has_time=True,
            priority=CalendarTask.Priority.NORMAL,
        )

        expected_date = nearest_task_date.isoformat()
        home_response = self.client.get(reverse('home'))
        main_response = self.client.get(reverse('calendar_main'), follow=True)

        self.assertEqual(home_response.context['initial_selected_date'], expected_date)
        self.assertEqual(main_response.context['initial_selected_date'], expected_date)
        self.assertEqual(self._sorted_event_source(home_response), self._sorted_event_source(main_response))
        self.assertEqual(self._sorted_task_source(home_response), self._sorted_task_source(main_response))

    def test_v2_authenticated_calendar_surface_defaults_to_latest_past_item_date(self):
        user = self._login('pastfocususer')
        today = timezone.localdate()
        older_event_date = today - timedelta(days=7)
        latest_task_date = today - timedelta(days=2)
        event_start = timezone.make_aware(datetime.combine(older_event_date, time(hour=9)))
        task_due = timezone.make_aware(datetime.combine(latest_task_date, time(hour=16)))
        self._create_calendar_event_with_note(
            user,
            title='지난주 상담 기록',
            note='과거 저장 일정도 홈 첫 진입에서 다시 보여야 함',
            start_time=event_start,
            end_time=event_start + timedelta(hours=1),
        )
        CalendarTask.objects.create(
            author=user,
            title='최근 완료한 후속 정리',
            note='기본 선택 날짜는 가장 최근 저장 일정이어야 함',
            due_at=task_due,
            has_time=True,
            priority=CalendarTask.Priority.HIGH,
        )

        expected_date = latest_task_date.isoformat()
        home_response = self.client.get(reverse('home'))
        main_response = self.client.get(reverse('calendar_main'), follow=True)

        self.assertEqual(home_response.context['initial_selected_date'], expected_date)
        self.assertEqual(main_response.context['initial_selected_date'], expected_date)
        self.assertEqual(self._sorted_event_source(home_response), self._sorted_event_source(main_response))
        self.assertEqual(self._sorted_task_source(home_response), self._sorted_task_source(main_response))

    def test_v2_authenticated_calendar_surface_matches_main_calendar_source(self):
        user = self._login('monthgriduser')
        now = timezone.now().replace(second=0, microsecond=0)
        self._create_calendar_event_with_note(
            user,
            title='월간 그리드 확인 일정',
            note='메인 숫자 달력에서도 표시되어야 함',
            start_time=now,
            end_time=now + timedelta(hours=1),
        )
        CalendarTask.objects.create(
            author=user,
            title='월간 그리드 할 일',
            note='오늘 할 일도 그리드에 반영',
            due_at=now,
            has_time=True,
            priority=CalendarTask.Priority.NORMAL,
        )

        today_key = timezone.localdate().isoformat()
        home_response = self.client.get(f"{reverse('home')}?date={today_key}")
        main_response = self.client.get(f"{reverse('calendar_main')}?date={today_key}", follow=True)
        content = home_response.content.decode('utf-8')

        self.assertIn('data-classcalendar-main-view="true"', content)
        self.assertIn('data-classcalendar-embed-mode="home"', content)
        self.assertEqual(home_response.context['initial_selected_date'], today_key)
        self.assertEqual(main_response.context['initial_selected_date'], today_key)
        self.assertEqual(self._sorted_event_source(home_response), self._sorted_event_source(main_response))
        self.assertEqual(self._sorted_task_source(home_response), self._sorted_task_source(main_response))
        self.assertIn(
            ('월간 그리드 확인 일정', '메인 숫자 달력에서도 표시되어야 함'),
            {
                (item['title'], item['note'])
                for item in self._sorted_event_source(home_response)
            },
        )
        self.assertIn(
            ('월간 그리드 할 일', '오늘 할 일도 그리드에 반영'),
            {
                (item['title'], item['note'])
                for item in self._sorted_task_source(home_response)
            },
        )
        self.assertNotIn('data-home-v2-calendar-month-grid="true"', content)
        self.assertNotIn('data-home-v2-calendar-day="true"', content)

    def test_v2_authenticated_calendar_surface_keeps_task_source_in_shared_data(self):
        user = self._login('taskslotuser')
        CalendarTask.objects.create(
            author=user,
            title='아침 조회 준비',
            note='출석부와 전달사항 확인',
            due_at=timezone.now().replace(second=0, microsecond=0),
            has_time=True,
            priority=CalendarTask.Priority.HIGH,
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        task_notes = {
            (item['title'], item['note'])
            for item in self._sorted_task_source(response)
        }

        self.assertIn('data-classcalendar-main-view="true"', content)
        self.assertIn(('아침 조회 준비', '출석부와 전달사항 확인'), task_notes)
        self.assertNotIn('data-home-v2-calendar-today-tasks="true"', content)

    def test_v2_authenticated_exposes_desktop_side_stack_for_favorites_and_community(self):
        user = self._login('balanceuser')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn("core/css/home_authenticated_v2.css", content)
        self.assertIn('data-home-v2-content-shell="true"', content)
        self.assertIn('data-home-v2-has-favorites="true"', content)
        self.assertIn('data-home-v2-side-stack="true"', content)
        self.assertIn('data-home-v2-favorites-grid="true"', content)
        self.assertIn('data-home-v2-favorites-panel="true"', content)
        self.assertIn('home-v2-community-zone', content)
        self.assertIn('home-v2-content-shell', content)
        self.assertIn('home-v2-top-zone', content)
        self.assertIn('data-classcalendar-day-modal="true"', content)
        self.assertIn('.classcalendar-day-cell', content)
        self.assertNotIn('function initHomeV2Interactions()', content)
        self.assertNotIn('function buildCalendarMessageHubState()', content)

    def test_v2_authenticated_has_sections(self):
        """V2 로그인 홈에 목적별 섹션 존재"""
        self._login('secuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('수합·서명', content)
        self.assertIn('문서·작성', content)

    def test_v2_authenticated_places_favorites_and_community_in_same_side_stack(self):
        user = self._login('tabletorder')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        top_zone_index = content.index('data-home-v2-top-zone="true"')
        side_stack_index = content.index('data-home-v2-side-stack="true"')
        favorites_index = content.index('data-home-v2-favorites-panel="true"')
        summary_index = content.index('data-home-v2-community-section="true"')
        service_index = content.index('data-home-v2-service-groups="true"')

        self.assertLess(top_zone_index, side_stack_index)
        self.assertLess(side_stack_index, service_index)
        self.assertLess(favorites_index, summary_index)

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
        self.assertIn('data-home-v2-service-card-access="true"', content)

    def test_v2_authenticated_favorite_cards_show_compact_body(self):
        user = self._login('favoritebodyuser')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-v2-favorite-card-header="true"', content)
        self.assertIn('data-home-v2-favorite-card-title="true"', content)
        self.assertIn('수업을 준비해요', content)

    def test_v2_authenticated_favorite_cards_strip_conflict_markers_from_messagebox_title(self):
        user = self._login('messageboxfavorite')
        messagebox = Product.objects.create(
            title='<<<<<<<HEAD 업무 메시지 보관함',
            description='보관 메시지 확인',
            price=0,
            is_active=True,
            service_type='classroom',
            launch_route_name='messagebox:main',
        )
        ProductFavorite.objects.create(user=user, product=messagebox, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('업무 메시지 보관함', content)
        self.assertNotIn('&lt;&lt;&lt;&lt;&lt;&lt;&lt;HEAD', content)
        self.assertNotIn('<<<<<<<HEAD', content)

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

    @override_settings(SHEETBOOK_ENABLED=True, SHEETBOOK_DISCOVERY_VISIBLE=True)
    def test_v2_home_includes_active_sheetbook_on_discovery_surfaces(self):
        visible_product = self._create_sheetbook_product()
        user = self._login('sheetbookvisiblev2')
        ProductFavorite.objects.create(user=user, product=visible_product, pin_order=1)
        ProductUsageLog.objects.create(user=user, product=visible_product, action='launch', source='home_quick')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('학급 기록 보드', content)
        self.assertNotIn('숨김 교무수첩', content)
        self.assertIn(visible_product.id, [item['product'].id for item in response.context.get('quick_actions', [])])
        self.assertIn(visible_product.id, [item['product'].id for item in response.context.get('favorite_items', [])])
        section_product_ids = []
        for section in response.context.get('sections', []):
            section_product_ids.extend(product.id for product in section.get('products', []))
            section_product_ids.extend(product.id for product in section.get('overflow_products', []))
        for section in response.context.get('aux_sections', []):
            section_product_ids.extend(product.id for product in section.get('products', []))
            section_product_ids.extend(product.id for product in section.get('overflow_products', []))
        self.assertIn(visible_product.id, section_product_ids)
        self.assertNotIn(visible_product.id, [product.id for product in response.context.get('games', [])])
        search_payload = json.loads(response.context['service_launcher_json'])
        self.assertIn('학급 기록 보드', [item['title'] for item in search_payload])

    def test_v2_home_hides_sheetbook_when_runtime_disabled(self):
        visible_product = self._create_sheetbook_product()
        user = self._login('sheetbookhiddenv2')
        ProductFavorite.objects.create(user=user, product=visible_product, pin_order=1)
        ProductUsageLog.objects.create(user=user, product=visible_product, action='launch', source='home_quick')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertNotIn('학급 기록 보드', content)
        self.assertNotIn(visible_product.id, [item['product'].id for item in response.context.get('quick_actions', [])])
        self.assertNotIn(visible_product.id, [item['product'].id for item in response.context.get('favorite_items', [])])
        self.assertFalse(response.context['sheetbook_workspace']['enabled'])
        search_payload = json.loads(response.context['service_launcher_json'])
        self.assertNotIn('학급 기록 보드', [item['title'] for item in search_payload])

    def test_v2_authenticated_top_favorites_use_compact_title_only_cards(self):
        user = self._login('favoritecompact')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        favorites_index = content.index('data-home-v2-favorites-panel="true"')
        favorites_end = content.index('data-home-v2-community-section="true"', favorites_index)
        favorites_block = content[favorites_index:favorites_end]

        self.assertIn('data-home-v2-favorites-grid="true"', favorites_block)
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

        favorites_index = content.index('data-home-v2-favorites-panel="true"')
        favorites_end = content.index('data-home-v2-community-section="true"', favorites_index)
        favorites_block = content[favorites_index:favorites_end]

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
        self.assertEqual(build_favorite_service_title("<<<<<<<HEAD 업무 메시지 보관함"), "업무 메시지 보관함")

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

        self.assertIn('data-home-v2-community-section="true"', content)
        self.assertIn('https://example.com/community.jpg', content)
        self.assertIn('원문 보기', content)

    def test_v2_anonymous_does_not_render_sns_sidebar_or_mobile_preview(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertNotIn('sns-full-section-v2', content)
        self.assertNotIn('aria-label="소통 글 상세 보기"', content)
        self.assertNotIn('data-home-sns-expand="true"', content)

    def test_v2_authenticated_uses_xl_breakpoint_for_sns_sidebar(self):
        self._login('breakpointuser')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-home-v2-community-section="true"', content)
        self.assertNotIn('hidden xl:block', content)
        self.assertNotIn('block xl:hidden', content)
        self.assertNotIn('data-home-v2-tablet-community-summary="true"', content)
        self.assertIn('data-home-v2-top-zone="true"', content)

    def test_v2_staff_home_restores_sns_controls(self):
        staff = _create_onboarded_user('staffsns', nickname='운영자')
        staff.is_staff = True
        staff.save(update_fields=['is_staff'])
        UserPolicyConsent.objects.create(
            user=staff,
            provider='direct',
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source='required_gate',
            ip_address='127.0.0.1',
            user_agent='test-agent',
        )
        self.client.login(username='staffsns', password='pass1234')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('실시간 소통', content)
        self.assertIn('공지 작성', content)
        self.assertIn('뉴스 검토', content)
        self.assertIn('인사이트 노출', content)
        self.assertIn('data-home-v2-top-calendar="true"', content)

    def test_v2_authenticated_notice_scope_excludes_news_link_cards(self):
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
        self.assertNotIn('원문 보기', content)

    def test_v2_htmx_feed_renders_pinned_notice_once_in_dedicated_section(self):
        author = _create_onboarded_user('pinnednoticeauthor')
        pinned_notice = Post.objects.create(
            author=author,
            content='꼭 확인할 공지',
            post_type='notice',
            is_notice_pinned=True,
            allow_notice_dismiss=True,
        )
        Post.objects.create(author=author, content='일반 소통 글')

        self._login('pinnednoticeviewer')
        response = self.client.get(reverse('home'), HTTP_HX_REQUEST='true')
        content = response.content.decode('utf-8')

        self.assertIn('상단 고정 공지', content)
        self.assertEqual(content.count('꼭 확인할 공지'), 1)
        self.assertIn(f'data-pinned-notice-key="{pinned_notice.pinned_notice_dismiss_key}"', content)

    def test_v2_htmx_feed_shows_close_button_only_for_dismissible_pinned_notice(self):
        author = _create_onboarded_user('dismissiblenoticeauthor')
        Post.objects.create(
            author=author,
            content='닫을 수 있는 공지',
            post_type='notice',
            is_notice_pinned=True,
            allow_notice_dismiss=True,
        )
        Post.objects.create(
            author=author,
            content='항상 보여야 하는 공지',
            post_type='notice',
            is_notice_pinned=True,
            allow_notice_dismiss=False,
        )

        self._login('dismissiblenoticeviewer')
        response = self.client.get(reverse('home'), HTTP_HX_REQUEST='true')
        content = response.content.decode('utf-8')

        self.assertEqual(content.count('data-pinned-notice-close'), 1)
        self.assertIn('닫을 수 있는 공지', content)
        self.assertIn('항상 보여야 하는 공지', content)

    def test_v2_staff_notice_create_saves_pin_and_dismiss_options(self):
        staff = _create_onboarded_user('staffnoticewriter')
        staff.is_staff = True
        staff.save(update_fields=['is_staff'])
        UserPolicyConsent.objects.create(
            user=staff,
            provider='direct',
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source='required_gate',
            ip_address='127.0.0.1',
            user_agent='test-agent',
        )
        self.client.login(username='staffnoticewriter', password='pass1234')

        response = self.client.post(
            reverse('post_create'),
            {
                'content': '상단 고정 새 공지',
                'submit_kind': 'notice',
                'pin_notice_to_top': '1',
                'allow_notice_dismiss': '1',
            },
            HTTP_HX_REQUEST='true',
        )

        created_post = Post.objects.get(content='상단 고정 새 공지')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(created_post.post_type, 'notice')
        self.assertTrue(created_post.is_notice_pinned)
        self.assertTrue(created_post.allow_notice_dismiss)

    def test_v2_authenticated_feed_renders_news_link_preview_image(self):
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

        self._login('newsviewer')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('교실 뉴스', content)
        self.assertIn('https://example.com/article.jpg', content)
        self.assertIn('원문 보기', content)
        self.assertNotIn('원문 보기 (새 탭)', content)

    def test_v2_anonymous_does_not_render_mobile_sns_toggle(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertNotIn('sns-full-section-v2', content)
        self.assertNotIn('소통창 열기', content)
        self.assertNotIn('aria-label="소통 글 상세 보기"', content)

    def test_v2_authenticated_mobile_sns_more_uses_toggle_not_anchor(self):
        self._login('v2authsns')
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('data-home-v2-community-section="true"', content)
        self.assertNotIn('@click="snsOpen = true"', content)
        self.assertNotIn('hx-select="#mobile-post-list-container"', content)
        self.assertNotIn('href="#sns-full-section-auth-v2"', content)

    def test_v2_authenticated_home_sns_shows_expand_button_after_two_posts(self):
        _create_posts()
        self._login('snsviewer')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-v2-community-section="true"', content)
        self.assertIn('data-home-sns-expand="true"', content)
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
        self.assertIn('더보기', content)

    def test_v2_community_feed_keeps_full_sns_list_without_home_expand_button(self):
        _create_posts(username='snscommunityauthor')

        response = self.client.get(reverse('community_feed'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], f"{reverse('home')}#home-community-section")


class HomeSupplementaryViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_community_feed_uses_separate_full_screen_surface(self):
        response = self.client.get(reverse('community_feed'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], f"{reverse('home')}#home-community-section")

    def test_home_search_payload_uses_is_active_and_public_names(self):
        Product.objects.create(
            title="간편 수합",
            description="수합 설명",
            price=0,
            is_active=True,
            service_type='collect_sign',
            launch_route_name='collect:landing',
        )
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
            is_active=False,
            service_type='classroom',
            launch_route_name='sheetbook:index',
        )

        response = self.client.get(reverse('home'))
        payload = json.loads(response.context['service_launcher_json'])
        titles = [item['title'] for item in payload]

        self.assertIn('간편 수합', titles)
        self.assertIn('학급 캘린더', titles)
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


class RepresentativeSlotSelectionTest(TestCase):
    def _build_sections(self, products):
        return [{'products': products, 'overflow_products': []}]

    def _create_product(self, title, *, display_order, service_type='classroom'):
        return Product.objects.create(
            title=title,
            description=f'{title} 설명',
            price=0,
            is_active=True,
            service_type=service_type,
            display_order=display_order,
        )

    def test_representative_slots_pin_top_used_products_and_rotate_unused_products(self):
        user = _create_onboarded_user('rep-fixed-user')
        p1 = self._create_product('많이 쓴 수업 도구', display_order=1)
        p2 = self._create_product('많이 쓴 행정 도구', display_order=2, service_type='work')
        p3 = self._create_product('가끔 쓴 상담 도구', display_order=3, service_type='counsel')
        p4 = self._create_product('안 써본 수업 도구 A', display_order=4)
        p5 = self._create_product('안 써본 수업 도구 B', display_order=5, service_type='work')
        p6 = self._create_product('안 써본 수업 도구 C', display_order=6, service_type='counsel')

        for _ in range(3):
            ProductUsageLog.objects.create(user=user, product=p1, action='launch', source='home_quick')
        for _ in range(2):
            ProductUsageLog.objects.create(user=user, product=p2, action='launch', source='home_quick')
        ProductUsageLog.objects.create(user=user, product=p3, action='launch', source='home_quick')

        frozen_day = date(2026, 3, 15)
        with patch('core.views.timezone.localdate', return_value=frozen_day):
            slots = _build_home_v4_representative_slots(
                user,
                favorite_products=[],
                recent_products=[p3, p2, p1],
                quick_actions=[p1, p2, p3],
                discovery_products=[p4, p5, p6],
                sections=self._build_sections([p1, p2, p3, p4, p5, p6]),
                aux_sections=[],
                games=[],
            )

        expected_rotating = _rotate_items(
            [p4, p5, p6],
            frozen_day.toordinal() + user.id,
        )[:2]

        self.assertEqual([slot['slot_kind'] for slot in slots], ['fixed', 'fixed', 'rotating', 'rotating'])
        self.assertEqual([slot['product'] for slot in slots[:2]], [p1, p2])
        self.assertEqual([slot['product'] for slot in slots[2:]], expected_rotating)

    def test_representative_slots_fill_rotation_with_low_usage_when_unused_pool_is_short(self):
        user = _create_onboarded_user('rep-fallback-user')
        p1 = self._create_product('상위 사용 도구 A', display_order=1)
        p2 = self._create_product('상위 사용 도구 B', display_order=2, service_type='work')
        p3 = self._create_product('가끔 쓰는 도구', display_order=3, service_type='counsel')
        p4 = self._create_product('아직 안 쓴 도구', display_order=4)

        for _ in range(4):
            ProductUsageLog.objects.create(user=user, product=p1, action='launch', source='home_quick')
        for _ in range(3):
            ProductUsageLog.objects.create(user=user, product=p2, action='launch', source='home_quick')
        ProductUsageLog.objects.create(user=user, product=p3, action='launch', source='home_quick')

        with patch('core.views.timezone.localdate', return_value=date(2026, 3, 15)):
            slots = _build_home_v4_representative_slots(
                user,
                favorite_products=[],
                recent_products=[p3, p2, p1],
                quick_actions=[p1, p2, p3],
                discovery_products=[p4],
                sections=self._build_sections([p1, p2, p3, p4]),
                aux_sections=[],
                games=[],
            )

        self.assertEqual([slot['product'] for slot in slots[:2]], [p1, p2])
        self.assertEqual([slot['slot_kind'] for slot in slots[:4]], ['fixed', 'fixed', 'rotating', 'rotating'])
        self.assertEqual([slot['product'] for slot in slots[2:4]], [p4, p3])


@override_settings(HOME_LAYOUT_VERSION='v4', HOME_V2_ENABLED=True)
class HomeV4ViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.collect_product = Product.objects.create(
            title="간편 수합",
            description="서명과 수합",
            price=0,
            is_active=True,
            service_type='collect_sign',
            launch_route_name='collect:landing',
            icon='fa-solid fa-inbox',
        )
        self.consent_product = Product.objects.create(
            title="동의서는 나에게 맡겨",
            description="동의서 회수",
            price=0,
            is_active=True,
            service_type='collect_sign',
            launch_route_name='consent:dashboard',
            icon='fa-solid fa-file-signature',
        )
        self.signature_product = Product.objects.create(
            title="가뿐하게 서명 톡",
            description="링크 서명",
            price=0,
            is_active=True,
            service_type='collect_sign',
            launch_route_name='signatures:list',
            icon='fa-solid fa-signature',
        )
        self.handoff_product = Product.objects.create(
            title="배부 체크",
            description="배부 확인",
            price=0,
            is_active=True,
            service_type='collect_sign',
            launch_route_name='handoff:landing',
            icon='fa-solid fa-box-open',
        )
        self.p1 = Product.objects.create(
            title="수업 도구",
            description="수업용",
            price=0,
            is_active=True,
            service_type='classroom',
            is_featured=True,
            launch_route_name='qrgen:landing',
            solve_text='수업을 준비해요',
        )
        self.p2 = Product.objects.create(
            title="행정 도구",
            description="행정용",
            price=0,
            is_active=True,
            service_type='work',
            launch_route_name='noticegen:main',
        )
        self.p3 = Product.objects.create(
            title="상담 도구",
            description="상담용",
            price=0,
            is_active=True,
            service_type='counsel',
        )
        self.p4 = Product.objects.create(
            title="테스트 게임",
            description="게임",
            price=0,
            is_active=True,
            service_type='game',
        )
        self.external_product = Product.objects.create(
            title="외부 가이드",
            description="외부 참고 자료",
            price=0,
            is_active=True,
            service_type='edutech',
            external_url='https://example.com/tool',
            icon='fa-solid fa-arrow-up-right-from-square',
        )
        _create_posts(count=2)

    def _login(self, username='v4user', nickname=None):
        user = _create_onboarded_user(username, nickname=nickname)
        self.client.login(username=username, password='pass1234')
        return user

    def test_v4_authenticated_home_uses_new_template_and_accordion_menu(self):
        user = self._login('v4layout')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)
        ProductUsageLog.objects.create(user=user, product=self.p2, action='launch', source='home_quick')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('core/css/home_authenticated_v4.css', content)
        self.assertIn('data-home-v4-shell="true"', content)
        self.assertIn('data-home-v4-nav="desktop"', content)
        self.assertIn('data-home-v4-nav="mobile"', content)
        self.assertIn('data-home-v4-nav-section="collect_sign"', content)
        self.assertIn('data-home-v4-tool-list="collect_sign"', content)
        self.assertIn('data-home-v4-home-panel="true"', content)
        self.assertIn('data-home-v4-representative-services="true"', content)
        self.assertIn('data-home-v4-sns-panel="true"', content)
        self.assertIn('home-v4-primary-stack', content)
        self.assertIn('home-v4-home-panel-section', content)
        self.assertIn('home-v4-side-stack', content)
        self.assertIn('home-v4-community-section', content)
        self.assertIn('home-v4-representative-section', content)
        self.assertIn('home-v4-top-favorites', content)
        self.assertIn('home-v4-top-sns', content)
        self.assertIn('data-home-v4-mobile-menu-trigger="true"', content)
        self.assertIn('data-home-v4-mobile-sheet="true"', content)
        self.assertIn('간편 수합', content)
        self.assertIn('동의서는 나에게 맡겨', content)
        self.assertIn('가뿐하게 서명 톡', content)
        self.assertIn('배부 체크', content)
        self.assertNotIn('data-home-v4-more-toggle="true"', content)
        self.assertNotIn('data-home-v4-active-panel=', content)
        self.assertNotIn('data-home-v4-section-panel=', content)
        self.assertNotIn('data-home-v2-favorites-panel="true"', content)
        self.assertIn('선생님들과 나누고 싶은 이야기가 있나요?', content)
        self.assertIn(f'hx-post="{reverse("post_create")}"', content)
        self.assertNotIn('data-home-v2-tablet-community-summary="true"', content)
        self.assertNotIn('더 많은 도구 보기', content)
        self.assertNotIn('data-home-v4-sns-preview-list="true"', content)
        self.assertNotIn('홈 요약은 그대로 두고, 필요한 도구만 펼쳐서 바로 찾습니다.', content)
        self.assertNotIn('최근 올라온 이야기만 간단히 확인하고 전체 소통으로 이어갑니다.', content)
        self.assertNotIn('자주 여는 도구를 홈에서 먼저 보여주고, 자세한 목록은 왼쪽 메뉴에서 바로 엽니다.', content)

        home_panel_index = content.index('data-home-v4-home-panel="true"')
        representative_index = content.index('data-home-v4-representative-services="true"')
        favorites_index = content.index('data-home-v4-favorites-panel="true"')
        sns_index = content.index('data-home-v4-sns-panel="true"')
        self.assertLess(home_panel_index, representative_index)
        self.assertLess(representative_index, favorites_index)
        self.assertLess(favorites_index, sns_index)

    @override_settings(HOME_V4_MOBILE_CALENDAR_FIRST_ENABLED=True)
    def test_v4_mobile_calendar_first_flag_swaps_hamburger_for_quick_tools(self):
        user = self._login('v4mobileflag')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)
        today = timezone.localdate()
        start_time = timezone.make_aware(datetime.combine(today, time(hour=9)))
        CalendarEvent.objects.create(
            title='아침 조회',
            author=user,
            start_time=start_time,
            end_time=start_time + timedelta(minutes=40),
            color='indigo',
            visibility=CalendarEvent.VISIBILITY_TEACHER,
        )
        CalendarTask.objects.create(
            author=user,
            title='가정통신문 확인',
            due_at=start_time,
            has_time=True,
            priority=CalendarTask.Priority.NORMAL,
        )

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        expected_date_label = f'{today.month}월 {today.day}일'

        self.assertIn('data-home-v4-mobile-calendar-first="true"', content)
        self.assertIn('data-home-v4-mobile-calendar-status-scroll="true"', content)
        self.assertIn('data-home-v4-mobile-calendar-status="true"', content)
        self.assertIn('data-home-v4-mobile-calendar-chip="date"', content)
        self.assertIn('data-home-v4-mobile-calendar-chip="events"', content)
        self.assertIn('data-home-v4-mobile-calendar-chip="tasks"', content)
        self.assertIn('data-home-v4-mobile-calendar-first-trigger="true"', content)
        self.assertIn('data-home-v4-mobile-quick-tools="true"', content)
        self.assertIn('data-home-v4-mobile-quick-item="true"', content)
        self.assertIn('data-home-v4-mobile-all-tools-button="true"', content)
        self.assertIn('home-v4-mobile-all-tools-trigger--icon', content)
        self.assertIn('aria-label="전체 도구 열기"', content)
        self.assertEqual(content.count('data-home-v4-mobile-all-tools-button="true"'), 1)
        self.assertIn(expected_date_label, content)
        self.assertIn('일정 1건', content)
        self.assertIn('할 일 1건', content)
        self.assertIn('자주 쓰는 도구', content)
        self.assertNotIn('오늘 학급 캘린더', content)
        self.assertNotIn('data-home-v4-mobile-menu-trigger="true"', content)

        home_panel_index = content.index('data-home-v4-home-panel="true"')
        mobile_quick_index = content.index('data-home-v4-mobile-quick-tools="true"')
        representative_index = content.index('data-home-v4-representative-services="true"')
        self.assertLess(home_panel_index, mobile_quick_index)
        self.assertLess(mobile_quick_index, representative_index)

    def test_v4_section_menu_lists_full_tool_links_without_switching_home_summary(self):
        self._login('v4section')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        nav_sections = response.context['home_v4_nav_sections']
        collect_section = next(section for section in nav_sections if section['key'] == 'collect_sign')

        self.assertGreaterEqual(collect_section['count'], 4)
        self.assertTrue(
            {'간편 수합', '동의서는 나에게 맡겨', '가뿐하게 서명 톡', '배부 체크'}.issubset(
                {product.title for product in collect_section['products']}
            )
        )
        self.assertIn(f'href="{reverse("collect:landing")}"', content)
        self.assertIn(f'href="{reverse("consent:dashboard")}"', content)
        self.assertIn(f'href="{reverse("signatures:list")}"', content)
        self.assertIn(f'href="{reverse("handoff:landing")}"', content)
        self.assertIn('href="https://example.com/tool"', content)
        self.assertIn('target="_blank" rel="noopener"', content)
        self.assertIn('data-home-v4-home-panel="true"', content)
        self.assertNotIn('data-home-v4-section-panel=', content)

    def test_v4_games_menu_restores_student_link_launcher(self):
        self._login('v4gameslink')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-v4-nav-section="games"', content)
        self.assertIn('data-home-v4-student-games-link="true"', content)
        self.assertIn('학생 링크', content)
        self.assertIn('studentGamesQrModal', content)
        self.assertIn('data-student-games-issue-url="/products/dutyticker/student-games/issue/"', content)
        self.assertNotIn('launch/?token=', content)

    def test_v4_section_menu_renders_icon_corner_favorite_badges(self):
        self._login('v4favoritebadge')

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('data-home-v4-tool-item="collect_sign"', content)
        self.assertIn('data-home-v4-tool-favorite-badge="true"', content)
        self.assertIn('aria-label="간편 수합 즐겨찾기 토글"', content)
        self.assertIn('class="home-v4-tool-favorite-badge favorite-toggle-btn', content)

    def test_v4_anonymous_home_falls_back_to_public_v2(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertNotIn('core/css/home_authenticated_v4.css', content)
        self.assertNotIn('data-home-v4-shell="true"', content)
        self.assertIn('지금 바로 써보기', content)
        self.assertIn('로그인 후 전체 열기', content)

    @override_settings(HOME_LAYOUT_VERSION='v2', HOME_V2_ENABLED=True)
    def test_setting_home_layout_version_to_v2_rolls_back_to_existing_authenticated_home(self):
        user = self._login('rollbackuser')
        ProductFavorite.objects.create(user=user, product=self.p1, pin_order=1)

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')

        self.assertIn('core/css/home_authenticated_v2.css', content)
        self.assertIn('data-home-v2-top-zone="true"', content)
        self.assertNotIn('core/css/home_authenticated_v4.css', content)
        self.assertNotIn('data-home-v4-shell="true"', content)


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
