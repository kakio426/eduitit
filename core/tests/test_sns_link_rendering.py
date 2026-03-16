from django.contrib.auth.models import AnonymousUser, User
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

from core.models import Comment, Post


class SnsLinkRenderingTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.author = User.objects.create_user(
            username="snslinkauthor",
            email="snslinkauthor@example.com",
            password="pass1234",
        )
        self.viewer = User.objects.create_user(
            username="snslinkviewer",
            email="snslinkviewer@example.com",
            password="pass1234",
        )

    def test_post_item_renders_urls_as_clickable_links(self):
        post = Post.objects.create(
            author=self.author,
            content="자료 링크 https://example.com/path 를 확인해 주세요.",
        )
        request = self.factory.get("/")
        request.user = self.viewer
        request.session = {}

        html = render_to_string(
            "core/partials/post_item.html",
            {"post": post, "user": self.viewer, "request": request},
            request=request,
        )

        self.assertIn('href="https://example.com/path"', html)
        self.assertIn(">https://example.com/path</a>", html)

    def test_comment_item_renders_urls_as_clickable_links(self):
        post = Post.objects.create(author=self.author, content="본문")
        comment = Comment.objects.create(
            post=post,
            author=self.author,
            content="참고 주소는 https://example.com/comment 입니다.",
        )
        request = self.factory.get("/")
        request.user = AnonymousUser()
        request.session = {}

        html = render_to_string(
            "core/partials/comment_item.html",
            {"comment": comment, "user": request.user, "request": request},
            request=request,
        )

        self.assertIn('href="https://example.com/comment"', html)
        self.assertIn(">https://example.com/comment</a>", html)
