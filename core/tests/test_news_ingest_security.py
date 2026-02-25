from unittest.mock import patch

from django.test import SimpleTestCase

from core.news_ingest import UnsafeNewsUrlError, assert_safe_public_url


class NewsIngestSafetyTests(SimpleTestCase):
    def test_blocks_localhost(self):
        with self.assertRaises(UnsafeNewsUrlError):
            assert_safe_public_url("http://localhost:8000/rss.xml")

    def test_blocks_private_ip_resolution(self):
        with patch("core.news_ingest.socket.getaddrinfo", return_value=[(None, None, None, None, ("10.0.0.2", 0))]):
            with self.assertRaises(UnsafeNewsUrlError):
                assert_safe_public_url("https://example.com/path")

    def test_allows_public_ip_resolution(self):
        with patch("core.news_ingest.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            normalized = assert_safe_public_url("https://example.com/path?utm_source=x")
        self.assertEqual(normalized, "https://example.com/path")

    def test_respects_allowed_host_suffixes(self):
        with patch("core.news_ingest.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            with self.assertRaises(UnsafeNewsUrlError):
                assert_safe_public_url(
                    "https://example.com/path",
                    allowed_host_suffixes=["allowed.com"],
                )

