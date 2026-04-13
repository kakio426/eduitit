from __future__ import annotations

import io
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from core.document_signing import get_pdf_bytes_from_file_field, normalize_pdf_bytes


class _CloudinaryPdfFieldStub:
    name = "media/docsign/source/2026/04/13/sample_pdf_asset"
    url = "https://res.cloudinary.com/demo/image/upload/v1/media/docsign/source/2026/04/13/sample_pdf_asset"
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
