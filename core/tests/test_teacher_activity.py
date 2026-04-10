import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Post,
    TeacherActivityEvent,
    TeacherActivityProfile,
    TeacherBuddyState,
    UserPolicyConsent,
    UserProfile,
)
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from core.teacher_activity import (
    ACTIVITY_CATEGORY_DAILY_LOGIN,
    ACTIVITY_CATEGORY_REQUEST_SENT,
    ACTIVITY_CATEGORY_SERVICE_USE,
    award_teacher_activity,
    backfill_teacher_activity,
    resolve_teacher_activity_level,
)
from core.teacher_buddy import ensure_teacher_buddy_state
from products.models import Product
from signatures.models import TrainingSession


def create_teacher(username: str) -> User:
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="pw123456",
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = username
    profile.role = "school"
    profile.save(update_fields=["nickname", "role"])
    UserPolicyConsent.objects.create(
        user=user,
        provider="direct",
        terms_version=TERMS_VERSION,
        privacy_version=PRIVACY_VERSION,
        agreed_at=timezone.now(),
        agreement_source="required_gate",
    )
    return user


@override_settings(HOME_TEACHER_BUDDY_ENABLED=True, HOME_V2_ENABLED=True)
class TeacherActivityServiceTests(TestCase):
    def setUp(self):
        self.client.force_login(create_teacher("viewer"))
        self.user = create_teacher("activityteacher")
        self.product_one = Product.objects.create(
            title="교실 보드",
            description="교실 보드",
            price=0,
            is_active=True,
            service_type="classroom",
            launch_route_name="classcalendar:main",
        )
        self.product_two = Product.objects.create(
            title="공지 정리",
            description="공지 정리",
            price=0,
            is_active=True,
            service_type="work",
            launch_route_name="noticegen:main",
        )
        self.product_three = Product.objects.create(
            title="수업 게임",
            description="수업 게임",
            price=0,
            is_active=True,
            service_type="game",
            launch_route_name="fairy_games:play_reversi",
        )
        ensure_teacher_buddy_state(self.user)

    def test_veteran_level_requires_three_years_of_active_days(self):
        current, _ = resolve_teacher_activity_level(total_score=5000, active_day_count=364)
        self.assertEqual(current.label, "탄탄")

        current, _ = resolve_teacher_activity_level(total_score=3200, active_day_count=1095)
        self.assertEqual(current.label, "베테랑")

    def test_daily_login_signal_awards_once_per_day(self):
        self.client.logout()
        self.client.login(username="activityteacher", password="pw123456")
        self.client.logout()
        self.client.login(username="activityteacher", password="pw123456")

        profile = TeacherActivityProfile.objects.get(user=self.user)
        self.assertEqual(profile.total_score, 1)
        self.assertEqual(
            TeacherActivityEvent.objects.filter(
                user=self.user,
                category=ACTIVITY_CATEGORY_DAILY_LOGIN,
            ).count(),
            1,
        )

    def test_track_usage_caps_at_two_distinct_products_per_day(self):
        self.client.force_login(self.user)
        for product in (self.product_one, self.product_two, self.product_three):
            response = self.client.post(
                reverse("track_product_usage"),
                data=json.dumps(
                    {
                        "product_id": product.id,
                        "action": "launch",
                        "source": "home_quick",
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)

        profile = TeacherActivityProfile.objects.get(user=self.user)
        self.assertEqual(profile.total_score, 2)
        self.assertEqual(profile.active_day_count, 1)
        self.assertEqual(
            TeacherActivityEvent.objects.filter(
                user=self.user,
                category=ACTIVITY_CATEGORY_SERVICE_USE,
            ).count(),
            2,
        )

    def test_public_profile_sheet_and_share_page_show_activity_summary(self):
        award_teacher_activity(
            self.user,
            category=ACTIVITY_CATEGORY_SERVICE_USE,
            source_key=f"product:{self.product_one.id}",
            occurred_at=timezone.now(),
            related_object=self.product_one,
        )
        award_teacher_activity(
            self.user,
            category=ACTIVITY_CATEGORY_REQUEST_SENT,
            source_key="consent:sample",
            occurred_at=timezone.now(),
            related_object_type="consent.signaturerequest",
            related_object_id="1",
        )
        state = TeacherBuddyState.objects.get(user=self.user)

        sheet_response = self.client.get(
            reverse("teacher_buddy_profile_sheet", kwargs={"public_share_token": state.public_share_token})
        )
        self.assertEqual(sheet_response.status_code, 200)
        self.assertContains(sheet_response, "활동 지수")
        self.assertContains(sheet_response, "누적 지수")
        self.assertContains(sheet_response, "3")

        share_response = self.client.get(
            reverse("teacher_buddy_share_page", kwargs={"public_share_token": state.public_share_token})
        )
        self.assertEqual(share_response.status_code, 200)
        self.assertContains(share_response, "활동일")
        self.assertContains(share_response, "검증된 활동만 반영")

    def test_feed_avatar_exposes_profile_sheet_trigger(self):
        viewer = create_teacher("feedviewer")
        post = Post.objects.create(
            author=self.user,
            content="메이트 시트를 열 수 있는지 확인하는 커뮤니티 글입니다.",
            post_type="general",
        )
        self.client.force_login(viewer)

        response = self.client.get(reverse("community_feed"), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        state = TeacherBuddyState.objects.get(user=self.user)
        self.assertContains(response, 'data-buddy-profile-trigger="true"')
        self.assertContains(
            response,
            reverse("teacher_buddy_profile_sheet", kwargs={"public_share_token": state.public_share_token}),
        )

    def test_backfill_teacher_activity_restores_usage_and_request_events(self):
        teacher = create_teacher("backfillteacher")
        now = timezone.now()
        yesterday = now - timezone.timedelta(days=1)
        for product in (self.product_one, self.product_two, self.product_three):
            log = teacher.product_usage_logs.create(
                product=product,
                action="launch",
                source="home_quick",
            )
            log.created_at = yesterday
            log.save(update_fields=["created_at"])

        session = TrainingSession.objects.create(
            title="백필 연수",
            print_title="백필 연수",
            instructor="담당 교사",
            datetime=now + timezone.timedelta(days=2),
            location="시청각실",
            description="백필",
            created_by=teacher,
            is_active=True,
        )
        TrainingSession.objects.filter(pk=session.pk).update(created_at=now)

        stats = backfill_teacher_activity()
        profile = TeacherActivityProfile.objects.get(user=teacher)

        self.assertGreaterEqual(stats["service_use_awarded"], 2)
        self.assertGreaterEqual(stats["request_sent_awarded"], 1)
        self.assertEqual(profile.total_score, 4)
        self.assertEqual(profile.active_day_count, 2)
        self.assertEqual(
            TeacherActivityEvent.objects.filter(
                user=teacher,
                category=ACTIVITY_CATEGORY_SERVICE_USE,
            ).count(),
            2,
        )
        self.assertEqual(
            TeacherActivityEvent.objects.filter(
                user=teacher,
                category=ACTIVITY_CATEGORY_REQUEST_SENT,
            ).count(),
            1,
        )
