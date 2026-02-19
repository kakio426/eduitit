import base64
import hashlib
import io
import logging
from datetime import datetime

from django.core.files.base import ContentFile
from django.utils import timezone

from .models import SignatureDocument, SignatureRecipient, SignatureRequest

logger = logging.getLogger(__name__)


def _split_data_url(data_url: str):
    if "," not in data_url:
        raise ValueError("Invalid data URL")
    _, payload = data_url.split(",", 1)
    return base64.b64decode(payload)


def _image_to_pdf_bytes(path: str):
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    image = ImageReader(path)
    width, height = image.getSize()
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(width, height))
    c.drawImage(image, 0, 0, width=width, height=height, preserveAspectRatio=True, mask="auto")
    c.showPage()
    c.save()
    packet.seek(0)
    return packet.read()


def get_document_pdf_bytes(document: SignatureDocument) -> bytes:
    path = document.original_file.path
    if document.file_type == SignatureDocument.FILE_TYPE_PDF:
        with open(path, "rb") as f:
            return f.read()
    return _image_to_pdf_bytes(path)


def guess_file_type(filename: str):
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return SignatureDocument.FILE_TYPE_PDF
    return SignatureDocument.FILE_TYPE_IMAGE


def hash_document_bytes(document: SignatureDocument) -> str:
    digest = hashlib.sha256(get_document_pdf_bytes(document)).hexdigest()
    return digest


def _resolve_font_name():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    for candidate in ("HYGothic-Medium", "HYSMyeongJo-Medium"):
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(candidate))
            return candidate
        except Exception:
            continue
    return "Helvetica"


def _status_label(recipient: SignatureRecipient) -> str:
    if recipient.status == SignatureRecipient.STATUS_SIGNED:
        return "동의 완료"
    if recipient.status == SignatureRecipient.STATUS_DECLINED:
        return "비동의 완료"
    return "미응답"


def _decision_label(recipient: SignatureRecipient) -> str:
    if recipient.decision == SignatureRecipient.DECISION_AGREE:
        return "동의"
    if recipient.decision == SignatureRecipient.DECISION_DISAGREE:
        return "비동의"
    return "-"


def _generate_minimal_summary_pdf(request: SignatureRequest) -> ContentFile:
    def escape_pdf_text(text: str) -> str:
        safe = (text or "").encode("ascii", errors="ignore").decode("ascii")
        return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines = [
        "Consent Summary",
        f"Title: {request.title or '-'}",
        f"Request ID: {request.request_id}",
        f"Created At: {timezone.localtime(request.created_at).strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    for idx, recipient in enumerate(request.recipients.order_by("id")[:12], start=1):
        decision = recipient.decision or "-"
        lines.append(f"{idx}. {recipient.student_name}/{recipient.parent_name} - {decision}")

    text_ops = []
    y = 800
    for line in lines:
        text_ops.append(f"BT /F1 11 Tf 40 {y} Td ({escape_pdf_text(line)}) Tj ET")
        y -= 18
    stream_text = "\n".join(text_ops)
    stream_bytes = stream_text.encode("ascii")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream_bytes)} >>\nstream\n{stream_text}\nendstream".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(f"{i} 0 obj\n".encode("ascii"))
        buffer.write(obj)
        buffer.write(b"\nendobj\n")

    xref_start = buffer.tell()
    buffer.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buffer.write(f"{off:010d} 00000 n \n".encode("ascii"))
    buffer.write(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("ascii")
    )
    buffer.seek(0)
    filename = f"summary_{request.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    return ContentFile(buffer.read(), name=filename)


def generate_summary_pdf(request: SignatureRequest) -> ContentFile:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except ModuleNotFoundError:
        return _generate_minimal_summary_pdf(request)

    try:
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        width, height = A4
        font_name = _resolve_font_name()
        title = request.title or "동의서 수합 결과"

        def draw_header():
            y = height - 40
            c.setFont(font_name, 16)
            c.drawString(32, y, "동의서 수합 요약")
            y -= 20
            c.setFont(font_name, 10)
            c.drawString(32, y, f"제목: {title}")
            y -= 14
            c.drawString(32, y, f"요청 ID: {request.request_id}")
            y -= 14
            c.drawString(32, y, f"생성 시각: {timezone.localtime(request.created_at).strftime('%Y-%m-%d %H:%M:%S')}")
            return y - 20

        y = draw_header()
        recipients = request.recipients.order_by("student_name", "id")

        for idx, recipient in enumerate(recipients, start=1):
            block_height = 124
            if y < block_height:
                c.showPage()
                y = draw_header()

            c.roundRect(28, y - block_height + 8, width - 56, block_height - 12, 8, stroke=1, fill=0)
            c.setFont(font_name, 10)
            c.drawString(40, y - 12, f"{idx}. 학생: {recipient.student_name} / 보호자: {recipient.parent_name}")
            c.drawString(40, y - 28, f"상태: {_status_label(recipient)}")
            c.drawString(200, y - 28, f"결과: {_decision_label(recipient)}")
            signed_at_text = (
                timezone.localtime(recipient.signed_at).strftime("%Y-%m-%d %H:%M:%S")
                if recipient.signed_at
                else "-"
            )
            c.drawString(40, y - 44, f"처리시각: {signed_at_text}")

            reason = recipient.decline_reason.strip() if recipient.decline_reason else ""
            if reason:
                c.drawString(40, y - 60, f"비동의 사유: {reason[:80]}")

            c.drawString(40, y - 76, "서명")
            c.rect(75, y - 95, 170, 34, stroke=1, fill=0)
            if (recipient.signature_data or "").startswith("data:image"):
                try:
                    image = ImageReader(io.BytesIO(_split_data_url(recipient.signature_data)))
                    c.drawImage(
                        image,
                        78,
                        y - 92,
                        width=164,
                        height=28,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                except Exception:
                    c.setFont(font_name, 9)
                    c.drawString(82, y - 82, "서명 이미지 로드 실패")
            else:
                c.setFont(font_name, 9)
                c.drawString(82, y - 82, "서명 없음")

            y -= block_height

        c.save()
        packet.seek(0)
        filename = f"summary_{request.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        return ContentFile(packet.read(), name=filename)
    except Exception:
        logger.exception("[consent] reportlab summary generation failed request_id=%s", request.request_id)
        return _generate_minimal_summary_pdf(request)


def generate_merged_pdf(request: SignatureRequest, include_decline_summary: bool = False) -> ContentFile:
    return generate_summary_pdf(request)
