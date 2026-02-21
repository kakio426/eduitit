import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from hwpxchat.utils.hwpx_parser import HwpxParseError, parse_hwpx_to_markdown


def _build_sample_hwpx_bytes():
    section_xml = """<?xml version="1.0" encoding="UTF-8"?>
<hp:section xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
  <hp:p><hp:run><hp:t>문단 텍스트</hp:t></hp:run></hp:p>
  <hp:tbl>
    <hp:tr>
      <hp:tc><hp:p><hp:run><hp:t>이름</hp:t></hp:run></hp:p></hp:tc>
      <hp:tc><hp:p><hp:run><hp:t>점수</hp:t></hp:run></hp:p></hp:tc>
    </hp:tr>
    <hp:tr>
      <hp:tc><hp:p><hp:run><hp:t>홍길동</hp:t></hp:run></hp:p></hp:tc>
      <hp:tc><hp:p><hp:run><hp:t>95</hp:t></hp:run></hp:p></hp:tc>
    </hp:tr>
  </hp:tbl>
</hp:section>
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Contents/section0.xml", section_xml)
    return buffer.getvalue()


class HwpxParserTests(SimpleTestCase):
    def test_parse_text_and_table_to_markdown(self):
        hwpx_bytes = _build_sample_hwpx_bytes()
        upload = SimpleUploadedFile(
            "sample.hwpx",
            hwpx_bytes,
            content_type="application/octet-stream",
        )

        markdown = parse_hwpx_to_markdown(upload)

        self.assertIn("문단 텍스트", markdown)
        self.assertIn("| 이름 | 점수 |", markdown)
        self.assertIn("| --- | --- |", markdown)
        self.assertIn("| 홍길동 | 95 |", markdown)

    def test_non_hwpx_extension_raises(self):
        hwpx_bytes = _build_sample_hwpx_bytes()
        upload = SimpleUploadedFile(
            "sample.hwp",
            hwpx_bytes,
            content_type="application/octet-stream",
        )

        with self.assertRaises(HwpxParseError):
            parse_hwpx_to_markdown(upload)

