from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings

from core.models import NewsSource, Post


class FetchNewsLinksCommandTests(TestCase):
    def setUp(self):
        self.source = NewsSource.objects.create(
            name="테스트 RSS",
            source_type="media",
            url="https://example.com/rss.xml",
            is_active=True,
        )
        self.author = User.objects.create_user(username="seeduser", password="pass1234")

    @override_settings(NEWS_INGEST_MAX_PENDING=1)
    def test_stops_when_pending_queue_is_over_limit(self):
        Post.objects.create(
            author=self.author,
            content="pending news",
            post_type="news_link",
            approval_status="pending",
            source_url="https://example.com/a",
        )
        with patch("core.management.commands.fetch_news_links.fetch_rss_entries") as mock_fetch:
            call_command("fetch_news_links")
            mock_fetch.assert_not_called()

