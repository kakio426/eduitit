from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Comment, CommentReport, Post, UserProfile
from products.models import Product


def _create_onboarded_user(username: str) -> User:
    user = User.objects.create_user(username=username, email=f"{username}@test.com", password="pass1234")
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = username
    profile.role = "school"
    profile.save()
    return user


@override_settings(HOME_V2_ENABLED=False)
class NewsModerationFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        Product.objects.create(
            title="테스트 서비스",
            description="설명",
            price=0,
            is_active=True,
            service_type="classroom",
        )

        self.author = _create_onboarded_user("author")
        self.post = Post.objects.create(
            author=self.author,
            content="테스트 게시글",
            approval_status="approved",
        )
        self.comment = Comment.objects.create(
            post=self.post,
            author=self.author,
            content="테스트 댓글",
        )

    def test_pending_news_is_hidden_from_home_feed(self):
        approved_news = Post.objects.create(
            author=self.author,
            content="승인 뉴스",
            post_type="news_link",
            approval_status="approved",
            source_url="https://example.com/approved",
            og_title="승인 기사",
        )
        Post.objects.create(
            author=self.author,
            content="대기 뉴스",
            post_type="news_link",
            approval_status="pending",
            source_url="https://example.com/pending",
            og_title="대기 기사",
        )

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        page_posts = list(response.context["posts"].object_list)

        self.assertIn(approved_news, page_posts)
        self.assertNotIn("대기 기사", response.content.decode("utf-8"))

    def test_comment_is_auto_hidden_after_three_distinct_reports(self):
        for username in ["r1", "r2", "r3"]:
            reporter = _create_onboarded_user(username)
            self.client.login(username=reporter.username, password="pass1234")
            response = self.client.post(
                reverse("comment_report", args=[self.comment.id]),
                {"reason": "spam"},
                HTTP_HX_REQUEST="true",
            )
            self.assertEqual(response.status_code, 200)

        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_hidden)
        self.assertEqual(self.comment.hidden_reason, "reports")
        self.assertEqual(self.comment.report_count, 3)

    def test_duplicate_report_from_same_user_counts_once(self):
        reporter = _create_onboarded_user("dup_reporter")
        self.client.login(username=reporter.username, password="pass1234")

        self.client.post(reverse("comment_report", args=[self.comment.id]), {"reason": "spam"}, HTTP_HX_REQUEST="true")
        self.client.post(reverse("comment_report", args=[self.comment.id]), {"reason": "spam"}, HTTP_HX_REQUEST="true")

        self.assertEqual(CommentReport.objects.filter(comment=self.comment).count(), 1)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.report_count, 1)

    def test_comment_create_rate_limit_blocks_second_request(self):
        writer = _create_onboarded_user("writer")
        self.client.login(username=writer.username, password="pass1234")

        first = self.client.post(
            reverse("comment_create", args=[self.post.id]),
            {"content": "첫 댓글"},
            HTTP_HX_REQUEST="true",
        )
        second = self.client.post(
            reverse("comment_create", args=[self.post.id]),
            {"content": "두 번째 댓글"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
