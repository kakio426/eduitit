from types import SimpleNamespace

from django.test import SimpleTestCase

from core.storage_urls import safe_storage_url


class SafeStorageUrlTests(SimpleTestCase):
    def test_returns_default_for_empty_field(self):
        self.assertEqual(safe_storage_url(None, default=""), "")

    def test_returns_storage_url_when_available(self):
        file_field = SimpleNamespace(url="/media/example.pdf", name="example.pdf")

        self.assertEqual(safe_storage_url(file_field), "/media/example.pdf")

    def test_returns_default_when_storage_raises_runtime_error(self):
        class BrokenField:
            name = "broken.pdf"

            @property
            def url(self):
                raise RuntimeError("storage unavailable")

        self.assertEqual(safe_storage_url(BrokenField(), default=""), "")

    def test_returns_default_when_storage_raises_value_error(self):
        class MissingField:
            name = "missing.pdf"

            @property
            def url(self):
                raise ValueError("missing file")

        self.assertEqual(safe_storage_url(MissingField(), default="fallback"), "fallback")
