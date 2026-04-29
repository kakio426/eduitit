from __future__ import annotations

import io
import base64
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from core.document_signing import (
    get_pdf_bytes_from_file_field,
    get_signature_image_bytes,
    normalize_pdf_bytes,
)


class _CloudinaryPdfFieldStub:
    name = "media/docsign/source/2026/04/13/sample_pdf_asset"
    url = "https://res.cloudinary.com/demo/image/upload/v1/media/docsign/source/2026/04/13/sample_pdf_asset"
    storage = type("CloudinaryStorageStub", (), {"__module__": "cloudinary_storage.storage"})()

    def open(self, mode="rb"):
        raise RuntimeError("401 Client Error: Unauthorized for url")


class _CloudinaryRawPdfFieldStub:
    name = "collect/templates/private-guide.pdf"
    url = "https://res.cloudinary.com/demo/raw/upload/v1/media/collect/templates/private-guide.pdf"
    storage = type("CloudinaryStorageStub", (), {"__module__": "cloudinary_storage.storage"})()

    def open(self, mode="rb"):
        raise RuntimeError("401 Client Error: Unauthorized for url")


@override_settings(USE_CLOUDINARY=True)
class DocumentSigningFallbackTests(SimpleTestCase):
    @patch("core.document_signing.requests.get")
    @patch("cloudinary.utils.private_download_url")
    def test_pdf_bytes_fall_back_to_private_download_url_when_storage_open_fails(self, private_download_url_mock, requests_get_mock):
        private_download_url_mock.side_effect = [
            "https://signed.example.com/image-upload.pdf",
            "https://signed.example.com/raw-upload.pdf",
        ]
        response = Mock()
        response.content = b"%PDF-1.4 fallback"
        response.raise_for_status.return_value = None
        response.close.return_value = None
        requests_get_mock.return_value = response

        payload = get_pdf_bytes_from_file_field(_CloudinaryPdfFieldStub(), file_type="pdf")

        self.assertEqual(payload, b"%PDF-1.4 fallback")
        private_download_url_mock.assert_any_call(
            "media/docsign/source/2026/04/13/sample_pdf_asset",
            "pdf",
            resource_type="image",
            type="upload",
        )
        requests_get_mock.assert_called_once_with("https://signed.example.com/image-upload.pdf", timeout=(5, 30))

    @patch("core.document_signing.requests.get")
    @patch("cloudinary.utils.private_download_url")
    def test_pdf_bytes_try_cloudinary_public_id_from_file_url_when_name_differs(self, private_download_url_mock, requests_get_mock):
        def signed_url(public_id, requested_format, *, resource_type, type):
            format_segment = requested_format or "original"
            return f"https://signed.example.com/{resource_type}/{format_segment}/{public_id}"

        def fetch_signed(url, *args, **kwargs):
            response = Mock()
            response.close.return_value = None
            if "/raw/original/media/collect/templates/private-guide.pdf" in url:
                response.content = b"%PDF-1.4 media public id"
                response.raise_for_status.return_value = None
            else:
                response.raise_for_status.side_effect = requests.HTTPError("not found")
            return response

        private_download_url_mock.side_effect = signed_url
        requests_get_mock.side_effect = fetch_signed

        payload = get_pdf_bytes_from_file_field(_CloudinaryRawPdfFieldStub(), file_type="pdf")

        self.assertEqual(payload, b"%PDF-1.4 media public id")
        private_download_url_mock.assert_any_call(
            "media/collect/templates/private-guide.pdf",
            "",
            resource_type="raw",
            type="upload",
        )
        self.assertTrue(any("media/collect/templates/private-guide.pdf" in call.args[0] for call in requests_get_mock.call_args_list))

    def test_normalize_pdf_bytes_flattens_page_rotation(self):
        try:
            from reportlab.pdfgen import canvas
            from pypdf import PdfReader, PdfWriter
        except ModuleNotFoundError:
            self.skipTest("pdf runtime unavailable")

        packet = io.BytesIO()
        pdf = canvas.Canvas(packet, pagesize=(400, 200))
        pdf.drawString(40, 140, "rotated")
        pdf.showPage()
        pdf.save()
        packet.seek(0)

        reader = PdfReader(packet)
        writer = PdfWriter()
        page = reader.pages[0]
        page.rotate(90)
        writer.add_page(page)
        rotated_payload = io.BytesIO()
        writer.write(rotated_payload)

        normalized = normalize_pdf_bytes(rotated_payload.getvalue())
        normalized_reader = PdfReader(io.BytesIO(normalized))
        normalized_page = normalized_reader.pages[0]

        self.assertEqual(int(getattr(normalized_page, "rotation", 0) or 0) % 360, 0)
        self.assertEqual(round(float(normalized_page.mediabox.width)), 200)
        self.assertEqual(round(float(normalized_page.mediabox.height)), 400)

    def test_signature_image_bytes_trim_transparent_margins(self):
        try:
            from PIL import Image, ImageDraw
        except ModuleNotFoundError:
            self.skipTest("Pillow unavailable")

        image = Image.new("RGBA", (400, 220), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.line((18, 160, 40, 120, 62, 150, 86, 98), fill=(15, 23, 42, 255), width=6)
        original = io.BytesIO()
        image.save(original, format="PNG")
        data_url = "data:image/png;base64," + base64.b64encode(original.getvalue()).decode("ascii")

        trimmed = get_signature_image_bytes(data_url)

        with Image.open(io.BytesIO(trimmed)) as trimmed_image:
            self.assertLess(trimmed_image.width, 160)
            self.assertLess(trimmed_image.height, 120)
