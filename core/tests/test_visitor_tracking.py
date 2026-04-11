import datetime
import uuid
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

from core.context_processors import visitor_counts
from core.middleware import VISITOR_IDENTITY_COOKIE_NAME, VisitorTrackingMiddleware
from core.models import PageViewLog, VisitorLog
from core.utils import get_unique_visitor_count, get_weekly_stats


def _attach_session(request):
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()


class VisitorTrackingMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = VisitorTrackingMiddleware(lambda request: HttpResponse("ok"))
        self.ip_address = "203.0.113.10"
        self.user_agent = "Mozilla/5.0"

    def _build_request(self, user=None, ip_address=None):
        request = self.factory.get(
            "/",
            REMOTE_ADDR=ip_address or self.ip_address,
            HTTP_USER_AGENT=self.user_agent,
        )
        request.user = user or AnonymousUser()
        _attach_session(request)
        return request

    def test_same_session_same_day_is_counted_once(self):
        request = self._build_request()

        first_response = self.middleware(request)
        self.middleware(request)

        self.assertEqual(VisitorLog.objects.filter(is_bot=False).count(), 1)
        log = VisitorLog.objects.get(is_bot=False)
        self.assertEqual(log.identity_type, VisitorLog.IDENTITY_SESSION)
        self.assertIn(VISITOR_IDENTITY_COOKIE_NAME, first_response.cookies)

    def test_different_sessions_on_same_ip_are_counted_separately(self):
        first_request = self._build_request()
        second_request = self._build_request()

        self.middleware(first_request)
        self.middleware(second_request)

        logs = VisitorLog.objects.filter(is_bot=False).order_by("visitor_key")
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs.values("visitor_key").distinct().count(), 2)
        self.assertTrue(all(log.ip_address == self.ip_address for log in logs))

    def test_anonymous_cookie_keeps_identity_stable_across_new_sessions(self):
        first_request = self._build_request()
        first_response = self.middleware(first_request)

        visitor_cookie = first_response.cookies[VISITOR_IDENTITY_COOKIE_NAME].value

        second_request = self._build_request()
        second_request.COOKIES[VISITOR_IDENTITY_COOKIE_NAME] = visitor_cookie

        second_response = self.middleware(second_request)

        logs = VisitorLog.objects.filter(is_bot=False)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.get().visitor_key, f"session:{visitor_cookie}")
        self.assertNotIn(VISITOR_IDENTITY_COOKIE_NAME, second_response.cookies)

    def test_anonymous_visit_is_upgraded_after_login(self):
        user = User.objects.create_user(username="teacher", password="password123")
        request = self._build_request()

        response = self.middleware(request)
        self.assertEqual(VisitorLog.objects.filter(is_bot=False).count(), 1)
        request.COOKIES[VISITOR_IDENTITY_COOKIE_NAME] = response.cookies[VISITOR_IDENTITY_COOKIE_NAME].value

        request.user = user
        self.middleware(request)

        self.assertEqual(VisitorLog.objects.filter(is_bot=False).count(), 1)
        log = VisitorLog.objects.get(is_bot=False)
        self.assertEqual(log.identity_type, VisitorLog.IDENTITY_USER)
        self.assertEqual(log.user, user)
        self.assertEqual(log.visitor_key, f"user:{user.pk}")

    def test_same_session_same_page_is_logged_once_per_day(self):
        request = self._build_request()
        request.resolver_match = SimpleNamespace(view_name="home", url_name="home")

        self.middleware(request)
        self.middleware(request)

        self.assertEqual(PageViewLog.objects.filter(is_bot=False).count(), 1)
        page_log = PageViewLog.objects.get(is_bot=False)
        self.assertEqual(page_log.path, "/")
        self.assertEqual(page_log.route_name, "home")
        self.assertEqual(page_log.identity_type, VisitorLog.IDENTITY_SESSION)

    def test_same_session_different_pages_are_logged_separately(self):
        first_request = self._build_request()
        first_request.resolver_match = SimpleNamespace(view_name="home", url_name="home")
        first_response = self.middleware(first_request)

        visitor_cookie = first_response.cookies[VISITOR_IDENTITY_COOKIE_NAME].value

        second_request = self.factory.get(
            "/about/",
            REMOTE_ADDR=self.ip_address,
            HTTP_USER_AGENT=self.user_agent,
        )
        second_request.user = AnonymousUser()
        second_request.COOKIES[VISITOR_IDENTITY_COOKIE_NAME] = visitor_cookie
        second_request.resolver_match = SimpleNamespace(view_name="about", url_name="about")
        _attach_session(second_request)

        self.middleware(second_request)

        page_logs = PageViewLog.objects.filter(is_bot=False).order_by("path")
        self.assertEqual(page_logs.count(), 2)
        self.assertEqual(list(page_logs.values_list("path", flat=True)), ["/", "/about/"])


class VisitorMetricsUtilsTest(TestCase):
    def _create_log(self, *, visitor_key, visit_date, ip_address):
        log = VisitorLog.objects.create(
            ip_address=ip_address,
            visitor_key=f"temp:{uuid.uuid4().hex}",
            identity_type=VisitorLog.IDENTITY_SESSION,
            is_bot=False,
        )
        VisitorLog.objects.filter(pk=log.pk).update(visit_date=visit_date, visitor_key=visitor_key)
        log.refresh_from_db()
        return log

    def test_weekly_metrics_count_distinct_visitors_in_range(self):
        today = timezone.localdate()
        week_start = today - datetime.timedelta(days=today.weekday())

        self._create_log(
            visitor_key="session:first",
            visit_date=week_start,
            ip_address="203.0.113.10",
        )
        self._create_log(
            visitor_key="session:first",
            visit_date=week_start + datetime.timedelta(days=1),
            ip_address="203.0.113.10",
        )
        self._create_log(
            visitor_key="session:second",
            visit_date=week_start + datetime.timedelta(days=2),
            ip_address="203.0.113.11",
        )

        self.assertEqual(
            get_unique_visitor_count(start_date=week_start, exclude_bots=True),
            2,
        )

        stats = get_weekly_stats(weeks=1, exclude_bots=True)
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["count"], 2)


class VisitorCountsContextTest(TestCase):
    def _create_log(self, *, visitor_key, visit_date, ip_address, is_bot=False):
        identity_type = VisitorLog.IDENTITY_BOT if is_bot else VisitorLog.IDENTITY_SESSION
        log = VisitorLog.objects.create(
            ip_address=ip_address,
            visitor_key=f"temp:{uuid.uuid4().hex}",
            identity_type=identity_type,
            is_bot=is_bot,
        )
        VisitorLog.objects.filter(pk=log.pk).update(visit_date=visit_date, visitor_key=visitor_key)
        log.refresh_from_db()
        return log

    def test_superuser_context_uses_unique_human_visitors(self):
        today = timezone.localdate()
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password123",
        )
        request = RequestFactory().get("/")
        request.user = admin
        _attach_session(request)

        self._create_log(
            visitor_key="session:first",
            visit_date=today,
            ip_address="203.0.113.10",
        )
        self._create_log(
            visitor_key="session:first",
            visit_date=today - datetime.timedelta(days=1),
            ip_address="203.0.113.10",
        )
        self._create_log(
            visitor_key="bot:203.0.113.99",
            visit_date=today,
            ip_address="203.0.113.99",
            is_bot=True,
        )

        context = visitor_counts(request)

        self.assertTrue(context["show_visitor_counts"])
        self.assertEqual(context["today_visitor_count"], 1)
        self.assertEqual(context["total_visitor_count"], 1)


class VisitorCountsNavigationRenderTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _create_log(self, *, visitor_key, visit_date, ip_address, is_bot=False):
        identity_type = VisitorLog.IDENTITY_BOT if is_bot else VisitorLog.IDENTITY_SESSION
        log = VisitorLog.objects.create(
            ip_address=ip_address,
            visitor_key=f"temp:{uuid.uuid4().hex}",
            identity_type=identity_type,
            is_bot=is_bot,
        )
        VisitorLog.objects.filter(pk=log.pk).update(visit_date=visit_date, visitor_key=visitor_key)
        log.refresh_from_db()
        return log

    def _render_base(self, user):
        request = self.factory.get("/test-base/")
        request.user = user
        _attach_session(request)
        request._messages = FallbackStorage(request)
        response = TemplateResponse(request, "base.html", {})
        response.render()
        return response

    def test_superuser_sees_visitor_counts_only_in_menu(self):
        admin = User.objects.create_superuser(
            username="menuadmin",
            email="menuadmin@example.com",
            password="password123",
        )
        self._create_log(
            visitor_key="session:desktop-menu",
            visit_date=timezone.localdate(),
            ip_address="203.0.113.30",
        )
        response = self._render_base(admin)

        self.assertContains(response, 'data-visitor-counts-menu="desktop"', html=False)
        self.assertContains(response, 'data-visitor-counts-menu="mobile"', html=False)
        self.assertNotContains(response, 'title="오늘 고유 방문자 / 누적 고유 방문자"', html=False)

    def test_non_superuser_does_not_render_visitor_count_menu_items(self):
        user = User.objects.create_user(
            username="regularuser",
            email="regular@example.com",
            password="password123",
        )
        response = self._render_base(user)

        self.assertNotContains(response, 'data-visitor-counts-menu="desktop"', html=False)
        self.assertNotContains(response, 'data-visitor-counts-menu="mobile"', html=False)
