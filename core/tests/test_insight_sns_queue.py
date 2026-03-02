from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Post, UserProfile
from core.views import _build_post_feed_queryset
from insights.models import Insight


def _create_onboarded_user(username, *, is_staff=False):
    user = User.objects.create_user(username=username, email=f"{username}@test.com", password="pass1234")
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = username
    profile.role = "school"
    profile.save()
    if is_staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])
    return user


class InsightSnsQueueTest(TestCase):
    def setUp(self):
        self.staff_user = _create_onboarded_user("staff_insight", is_staff=True)
        self.normal_user = _create_onboarded_user("normal_insight", is_staff=False)
        self.insight = Insight.objects.create(
            title="테스트 인사이트",
            category="youtube",
            video_url="https://www.youtube.com/watch?v=abcd1234xyz",
            thumbnail_url="https://img.youtube.com/vi/abcd1234xyz/maxresdefault.jpg",
            content="SNS 상단 노출 테스트 인사이트 내용입니다.",
            tags="#테스트,#인사이트",
        )

    def test_staff_can_feature_insight_and_feed_prioritizes_it(self):
        self.client.login(username=self.staff_user.username, password="pass1234")
        response = self.client.post(
            reverse("insight_sns_action", args=[self.insight.id]),
            {"action": "feature"},
        )

        self.assertEqual(response.status_code, 302)
        detail_url = reverse("insights:detail", args=[self.insight.id])
        featured_post = Post.objects.get(
            post_type="news_link",
            publisher="Insight Library",
            source_url=detail_url,
        )
        self.assertIsNotNone(featured_post.featured_from)
        self.assertIsNotNone(featured_post.featured_until)
        self.assertGreater(featured_post.featured_until, featured_post.featured_from)
        self.assertEqual(featured_post.approval_status, "approved")

        Post.objects.create(
            author=self.staff_user,
            content="일반 최신 글",
            post_type="general",
            approval_status="approved",
        )

        feed = list(_build_post_feed_queryset()[:2])
        self.assertEqual(feed[0].id, featured_post.id)

    def test_staff_can_clear_featured_window(self):
        self.client.login(username=self.staff_user.username, password="pass1234")
        start_at = (timezone.now() - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
        end_at = (timezone.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        self.client.post(
            reverse("insight_sns_action", args=[self.insight.id]),
            {"action": "feature", "featured_from": start_at, "featured_until": end_at},
        )

        response = self.client.post(
            reverse("insight_sns_action", args=[self.insight.id]),
            {"action": "clear"},
        )

        self.assertEqual(response.status_code, 302)
        detail_url = reverse("insights:detail", args=[self.insight.id])
        featured_post = Post.objects.get(source_url=detail_url, publisher="Insight Library")
        self.assertIsNone(featured_post.featured_from)
        self.assertIsNone(featured_post.featured_until)

    def test_non_staff_cannot_access_queue_or_action(self):
        self.client.login(username=self.normal_user.username, password="pass1234")

        queue_response = self.client.get(reverse("insight_sns_queue"))
        self.assertEqual(queue_response.status_code, 302)

        action_response = self.client.post(
            reverse("insight_sns_action", args=[self.insight.id]),
            {"action": "feature"},
        )
        self.assertEqual(action_response.status_code, 403)
