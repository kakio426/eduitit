from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import NewsSource, Post
from core.news_ingest import ParsedEntry


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

    def test_skips_non_education_news_by_default(self):
        entries = [
            ParsedEntry(
                title="월드컵 결승 경기 결과",
                link="https://example.com/general-news",
                description="스포츠 경기 소식",
                published_at=timezone.now(),
            )
        ]

        with (
            patch(
                "core.management.commands.fetch_news_links.fetch_rss_entries",
                return_value=entries,
            ),
            patch(
                "core.management.commands.fetch_news_links.assert_safe_public_url",
                side_effect=lambda url, allowed_host_suffixes=None: url,
            ),
            patch(
                "core.management.commands.fetch_news_links.extract_og_metadata",
                return_value={
                    "title": "월드컵 결승 경기 결과",
                    "description": "스포츠 경기 소식",
                    "image_url": "",
                    "canonical_url": "https://example.com/general-news",
                    "published_at": timezone.now(),
                    "final_url": "https://example.com/general-news",
                    "publisher": "example.com",
                },
            ),
        ):
            call_command("fetch_news_links", "--source-id", str(self.source.id))

        self.assertEqual(Post.objects.filter(post_type="news_link").count(), 0)

    def test_keeps_education_ai_news_by_default(self):
        entries = [
            ParsedEntry(
                title="서울교육청, AI 디지털교과서 수업 확대",
                link="https://example.com/edu-ai-news",
                description="교사 연수와 학교 적용 지원 방안 발표",
                published_at=timezone.now(),
            )
        ]

        with (
            patch(
                "core.management.commands.fetch_news_links.fetch_rss_entries",
                return_value=entries,
            ),
            patch(
                "core.management.commands.fetch_news_links.assert_safe_public_url",
                side_effect=lambda url, allowed_host_suffixes=None: url,
            ),
            patch(
                "core.management.commands.fetch_news_links.extract_og_metadata",
                return_value={
                    "title": "서울교육청, AI 디지털교과서 수업 확대",
                    "description": "교사 연수와 학교 적용 지원 방안 발표",
                    "image_url": "",
                    "canonical_url": "https://example.com/edu-ai-news",
                    "published_at": timezone.now(),
                    "final_url": "https://example.com/edu-ai-news",
                    "publisher": "example.com",
                },
            ),
        ):
            call_command("fetch_news_links", "--source-id", str(self.source.id))

        news_posts = Post.objects.filter(post_type="news_link")
        self.assertEqual(news_posts.count(), 1)
        self.assertIn("AI", news_posts.first().og_title)

    def test_allow_general_option_includes_non_education_news(self):
        entries = [
            ParsedEntry(
                title="월드컵 결승 경기 결과",
                link="https://example.com/general-news-allowed",
                description="스포츠 경기 소식",
                published_at=timezone.now(),
            )
        ]

        with (
            patch(
                "core.management.commands.fetch_news_links.fetch_rss_entries",
                return_value=entries,
            ),
            patch(
                "core.management.commands.fetch_news_links.assert_safe_public_url",
                side_effect=lambda url, allowed_host_suffixes=None: url,
            ),
            patch(
                "core.management.commands.fetch_news_links.extract_og_metadata",
                return_value={
                    "title": "월드컵 결승 경기 결과",
                    "description": "스포츠 경기 소식",
                    "image_url": "",
                    "canonical_url": "https://example.com/general-news-allowed",
                    "published_at": timezone.now(),
                    "final_url": "https://example.com/general-news-allowed",
                    "publisher": "example.com",
                },
            ),
        ):
            call_command(
                "fetch_news_links",
                "--source-id",
                str(self.source.id),
                "--allow-general",
            )

        self.assertEqual(Post.objects.filter(post_type="news_link").count(), 1)
