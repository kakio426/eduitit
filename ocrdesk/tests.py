import base64
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.context_processors import search_products
from products.models import ManualSection, Product, ProductFeature, ServiceManual

from . import services as ocr_services
from .forms import MAX_IMAGE_BYTES
from .services import OCREngineUnavailable


User = get_user_model()

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+nYJ8AAAAASUVORK5CYII="
)


@override_settings(ONBOARDING_EXEMPT_PATH_PREFIXES=["/ocrdesk/"])
class OCRDeskViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ocrdesk_teacher",
            password="pw12345",
            email="ocrdesk_teacher@example.com",
        )
        profile = self.user.userprofile
        profile.nickname = "담임"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def _image_file(self, *, name="board.png", content_type="image/png", payload=None):
        return SimpleUploadedFile(name, payload or PNG_BYTES, content_type=content_type)

    def test_login_required_for_main_page(self):
        self.client.logout()

        response = self.client.get(reverse("ocrdesk:main"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_main_page_renders_for_teacher(self):
        response = self.client.get(reverse("ocrdesk:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "사진 한 장 올리고 바로 글자 확인")
        self.assertContains(response, "여기에 사진을 놓거나 눌러서 고르세요")
        self.assertContains(response, "지금 글자 읽기")
        self.assertEqual(response["Cache-Control"], "private, no-cache, must-revalidate")

    @patch("ocrdesk.views.extract_text_from_upload", return_value="숙제\n수학 익힘책 12쪽")
    def test_post_renders_editable_ocr_result(self, mocked_extract):
        response = self.client.post(
            reverse("ocrdesk:main"),
            {"image": self._image_file()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "숙제")
        self.assertContains(response, "수학 익힘책 12쪽")
        self.assertContains(response, "결과 복사")
        self.assertContains(response, "결과가 여기 채워집니다.")
        mocked_extract.assert_called_once()

    @patch("ocrdesk.views.extract_text_from_upload", return_value="준비물\n색연필")
    def test_htmx_post_returns_result_partial(self, mocked_extract):
        response = self.client.post(
            reverse("ocrdesk:main"),
            {"image": self._image_file()},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="ocrdesk-result-panel"', html=False)
        self.assertContains(response, 'hx-swap-oob="innerHTML"', html=False)
        self.assertContains(response, "준비물")
        mocked_extract.assert_called_once()

    def test_invalid_mime_shows_inline_error(self):
        response = self.client.post(
            reverse("ocrdesk:main"),
            {"image": self._image_file(content_type="text/plain")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "휴대폰 사진(JPG, PNG, WEBP)만 읽을 수 있습니다.")

    def test_invalid_extension_shows_inline_error(self):
        response = self.client.post(
            reverse("ocrdesk:main"),
            {"image": self._image_file(name="board.gif", content_type="image/gif")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "JPG, PNG, WEBP 사진만 올릴 수 있습니다.")

    def test_oversized_image_shows_inline_error(self):
        response = self.client.post(
            reverse("ocrdesk:main"),
            {
                "image": self._image_file(
                    payload=b"a" * (MAX_IMAGE_BYTES + 1),
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "사진은 10MB 이하만 올릴 수 있습니다.")

    def test_empty_submit_shows_required_error(self):
        response = self.client.post(reverse("ocrdesk:main"), {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "사진을 먼저 골라 주세요.")

    @patch("ocrdesk.views.extract_text_from_upload", side_effect=RuntimeError("boom"))
    def test_unexpected_runtime_error_shows_teacher_friendly_message(self, mocked_extract):
        response = self.client.post(
            reverse("ocrdesk:main"),
            {"image": self._image_file()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "사진을 읽는 중 문제가 생겼습니다.")
        mocked_extract.assert_called_once()


class OCRDeskServiceTests(SimpleTestCase):
    def tearDown(self):
        ocr_services.reset_ocr_engine_state()

    def test_build_engine_prefers_direct_bos_download_without_healthcheck_gate(self):
        fake_engine = object()
        fake_constructor = Mock(return_value=fake_engine)
        fake_module = SimpleNamespace(PaddleOCR=fake_constructor)

        with patch("ocrdesk.services.os.environ.setdefault") as mocked_setdefault:
            with patch("ocrdesk.services._get_cpu_threads", return_value=2):
                with patch.dict(sys.modules, {"paddleocr": fake_module}):
                    engine = ocr_services._build_engine()

        self.assertIs(engine, fake_engine)
        mocked_setdefault.assert_any_call("PADDLE_PDX_MODEL_SOURCE", "BOS")
        mocked_setdefault.assert_any_call("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        fake_constructor.assert_called_once_with(
            lang="korean",
            device="cpu",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
            enable_cinn=False,
            cpu_threads=2,
        )

    def test_get_cpu_threads_uses_safe_default_on_invalid_input(self):
        with patch.dict("ocrdesk.services.os.environ", {"OCRDESK_CPU_THREADS": "nope"}, clear=False):
            self.assertEqual(ocr_services._get_cpu_threads(), 2)

    def test_get_cpu_threads_clamps_to_positive_integer(self):
        with patch.dict("ocrdesk.services.os.environ", {"OCRDESK_CPU_THREADS": "0"}, clear=False):
            self.assertEqual(ocr_services._get_cpu_threads(), 1)

        with patch.dict("ocrdesk.services.os.environ", {"OCRDESK_CPU_THREADS": "6"}, clear=False):
            self.assertEqual(ocr_services._get_cpu_threads(), 6)

    def test_get_ocr_engine_retries_after_cooldown_when_first_init_fails(self):
        fake_engine = object()

        with patch("ocrdesk.services._get_init_retry_cooldown_seconds", return_value=1.0):
            with patch("ocrdesk.services.monotonic", side_effect=[0.0, 0.0, 0.5, 2.0, 2.0]):
                with patch("ocrdesk.services._build_engine", side_effect=[RuntimeError("boom"), fake_engine]) as mocked_build:
                    with self.assertRaises(OCREngineUnavailable):
                        ocr_services.get_ocr_engine()

                    with self.assertRaises(OCREngineUnavailable):
                        ocr_services.get_ocr_engine()

                    self.assertIs(ocr_services.get_ocr_engine(), fake_engine)

        self.assertEqual(mocked_build.call_count, 2)


class EnsureOCRDeskCommandTests(TestCase):
    def test_ensure_command_creates_service_assets_without_duplicates(self):
        call_command("ensure_ocrdesk")
        call_command("ensure_ocrdesk")

        product = Product.objects.get(launch_route_name="ocrdesk:main")

        self.assertEqual(product.title, "사진 글자 읽기")
        self.assertEqual(product.service_type, "work")
        self.assertFalse(product.is_guest_allowed)
        self.assertEqual(Product.objects.filter(launch_route_name="ocrdesk:main").count(), 1)
        self.assertEqual(ProductFeature.objects.filter(product=product).count(), 3)

        manual = ServiceManual.objects.get(product=product)
        self.assertTrue(manual.is_published)
        self.assertEqual(ManualSection.objects.filter(manual=manual).count(), 3)

    def test_service_launcher_payload_points_to_ocrdesk_route(self):
        call_command("ensure_ocrdesk")

        context = search_products(RequestFactory().get("/"))
        payload = json.loads(context["service_launcher_json"])

        item = next(item for item in payload if item["title"] == "사진 글자 읽기")
        self.assertEqual(item["group_key"], "doc_write")
        self.assertEqual(item["href"], reverse("ocrdesk:main"))
        self.assertFalse(item["is_external"])

    def test_ensure_command_preserves_admin_managed_copy(self):
        product = Product.objects.create(
            title="커스텀 사진 읽기",
            lead_text="관리자가 바꾼 소개",
            description="관리자가 바꾼 설명",
            price=99,
            is_active=True,
            is_guest_allowed=True,
            service_type="etc",
            icon="🪄",
            external_url="https://example.com/old",
            launch_route_name="ocrdesk:main",
            solve_text="관리자가 바꾼 solve",
            result_text="관리자가 바꾼 result",
            time_text="9분",
        )
        manual = ServiceManual.objects.create(
            product=product,
            title="커스텀 가이드",
            description="커스텀 설명",
            is_published=False,
        )

        call_command("ensure_ocrdesk")

        product.refresh_from_db()
        manual.refresh_from_db()

        self.assertEqual(product.title, "커스텀 사진 읽기")
        self.assertEqual(product.lead_text, "관리자가 바꾼 소개")
        self.assertEqual(product.description, "관리자가 바꾼 설명")
        self.assertEqual(product.price, 99)
        self.assertEqual(product.icon, "🪄")
        self.assertEqual(product.solve_text, "관리자가 바꾼 solve")
        self.assertEqual(product.result_text, "관리자가 바꾼 result")
        self.assertEqual(product.time_text, "9분")
        self.assertEqual(product.service_type, "work")
        self.assertFalse(product.is_guest_allowed)
        self.assertEqual(product.external_url, "")
        self.assertEqual(manual.title, "커스텀 가이드")
        self.assertEqual(manual.description, "커스텀 설명")
        self.assertFalse(manual.is_published)

    def test_ensure_command_does_not_duplicate_renamed_features_or_sections(self):
        product = Product.objects.create(
            title="사진 글자 읽기",
            description="설명",
            price=0,
            is_active=True,
            service_type="work",
            launch_route_name="ocrdesk:main",
        )
        ProductFeature.objects.create(
            product=product,
            icon="✅",
            title="관리자 이름 1",
            description="관리자 설명 1",
        )
        ProductFeature.objects.create(
            product=product,
            icon="✅",
            title="관리자 이름 2",
            description="관리자 설명 2",
        )
        ProductFeature.objects.create(
            product=product,
            icon="✅",
            title="관리자 이름 3",
            description="관리자 설명 3",
        )
        manual = ServiceManual.objects.create(
            product=product,
            title="관리자 가이드",
            description="관리자 가이드 설명",
            is_published=True,
        )
        ManualSection.objects.create(
            manual=manual,
            title="관리자 섹션 1",
            content="관리자 본문 1",
            display_order=10,
        )
        ManualSection.objects.create(
            manual=manual,
            title="관리자 섹션 2",
            content="관리자 본문 2",
            display_order=20,
        )
        ManualSection.objects.create(
            manual=manual,
            title="관리자 섹션 3",
            content="관리자 본문 3",
            display_order=30,
        )

        call_command("ensure_ocrdesk")

        self.assertEqual(ProductFeature.objects.filter(product=product).count(), 3)
        self.assertEqual(ManualSection.objects.filter(manual=manual).count(), 3)
        self.assertEqual(
            list(ProductFeature.objects.filter(product=product).values_list("title", flat=True)),
            ["관리자 이름 1", "관리자 이름 2", "관리자 이름 3"],
        )
        self.assertEqual(
            list(ManualSection.objects.filter(manual=manual).order_by("display_order").values_list("title", flat=True)),
            ["관리자 섹션 1", "관리자 섹션 2", "관리자 섹션 3"],
        )
