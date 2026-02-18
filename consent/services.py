import base64
import hashlib
import io
from datetime import datetime

from django.core.files.base import ContentFile
from django.utils import timezone

from .models import SignatureDocument, SignaturePosition, SignatureRecipient, SignatureRequest


def _split_data_url(data_url: str):
    if "," not in data_url:
        raise ValueError("Invalid data URL")
    _, payload = data_url.split(",", 1)
    return base64.b64decode(payload)


def _load_pdf_reader(path: str):
    from pypdf import PdfReader

    return PdfReader(path)


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


def get_document_reader(document: SignatureDocument):
    from pypdf import PdfReader

    return PdfReader(io.BytesIO(get_document_pdf_bytes(document)))


def create_signature_overlay(position: SignaturePosition, page_width: float, page_height: float, signature_data: str, footer_text: str):
    from pypdf import PdfReader
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))

    # Draw signature image inside configured rectangle.
    image = ImageReader(io.BytesIO(_split_data_url(signature_data)))
    c.drawImage(
        image,
        position.x,
        position.y,
        width=position.width,
        height=position.height,
        preserveAspectRatio=True,
        mask="auto",
    )

    c.setFont("Helvetica", 8)
    c.drawString(16, 12, footer_text[:240])
    c.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]


def create_declined_watermark(page_width: float, page_height: float):
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))
    c.saveState()
    c.setFillColorRGB(0.85, 0.1, 0.1)
    if hasattr(c, "setFillAlpha"):
        c.setFillAlpha(0.18)
    c.translate(page_width / 2, page_height / 2)
    c.rotate(30)
    c.setFont("Helvetica-Bold", 56)
    c.drawCentredString(0, 0, "비동의")
    c.restoreState()
    c.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]


def create_position_preview_overlay(position: SignaturePosition, page_width: float, page_height: float):
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas

    x, y, width, height = resolve_position(position, page_width, page_height)
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))
    c.setStrokeColorRGB(0.2, 0.4, 0.9)
    c.setLineWidth(1.2)
    c.rect(x, y, width, height)
    c.setFont("Helvetica", 9)
    c.drawString(x + 4, y + height - 12, "서명 위치 미리보기")
    c.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]


def resolve_position(position: SignaturePosition, page_width: float, page_height: float):
    if None not in (position.x_ratio, position.y_ratio, position.w_ratio, position.h_ratio):
        x = float(position.x_ratio) * page_width
        y = float(position.y_ratio) * page_height
        width = float(position.w_ratio) * page_width
        height = float(position.h_ratio) * page_height
        return x, y, width, height
    return position.x, position.y, position.width, position.height


def generate_signed_pdf(recipient: SignatureRecipient) -> ContentFile:
    from pypdf import PdfReader, PdfWriter

    request = recipient.request
    reader = PdfReader(io.BytesIO(get_document_pdf_bytes(request.document)))
    writer = PdfWriter()

    audit_time = timezone.localtime(recipient.signed_at or timezone.now()).strftime("%Y-%m-%d %H:%M:%S")
    footer = (
        f"Digitally Signed by {recipient.parent_name} at {audit_time} "
        f"(IP: {recipient.ip_address or '-'}) - Request ID: {request.request_id}"
    )

    positions = list(request.positions.all())
    positions_by_page = {}
    for position in positions:
        positions_by_page.setdefault(position.page, []).append(position)

    for page_index, page in enumerate(reader.pages, start=1):
        if page_index in positions_by_page:
            for position in positions_by_page[page_index]:
                x, y, width, height = resolve_position(position, float(page.mediabox.width), float(page.mediabox.height))
                temp_position = SignaturePosition(
                    page=position.page,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                )
                overlay_page = create_signature_overlay(
                    position=temp_position,
                    page_width=float(page.mediabox.width),
                    page_height=float(page.mediabox.height),
                    signature_data=recipient.signature_data,
                    footer_text=footer,
                )
                page.merge_page(overlay_page)
        if recipient.decision == SignatureRecipient.DECISION_DISAGREE:
            watermark = create_declined_watermark(float(page.mediabox.width), float(page.mediabox.height))
            page.merge_page(watermark)
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    filename = f"recipient_{recipient.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    return ContentFile(output.read(), name=filename)


def generate_merged_pdf(request: SignatureRequest, include_decline_summary: bool = False) -> ContentFile:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    recipients = request.recipients.filter(status=SignatureRecipient.STATUS_SIGNED, signed_pdf__isnull=False).order_by("student_name", "id")
    for recipient in recipients:
        with recipient.signed_pdf.open("rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                writer.add_page(page)

    if include_decline_summary:
        summary_page = create_decline_summary_page(request)
        if summary_page is not None:
            writer.add_page(summary_page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    filename = f"merged_{request.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    return ContentFile(output.read(), name=filename)


def guess_file_type(filename: str):
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return SignatureDocument.FILE_TYPE_PDF
    return SignatureDocument.FILE_TYPE_IMAGE


def hash_document_bytes(document: SignatureDocument) -> str:
    digest = hashlib.sha256(get_document_pdf_bytes(document)).hexdigest()
    return digest


def generate_position_preview_pdf(request: SignatureRequest) -> ContentFile:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(get_document_pdf_bytes(request.document)))
    writer = PdfWriter()
    positions_by_page = {}
    for position in request.positions.all():
        positions_by_page.setdefault(position.page, []).append(position)

    for page_index, page in enumerate(reader.pages, start=1):
        for position in positions_by_page.get(page_index, []):
            overlay = create_position_preview_overlay(position, float(page.mediabox.width), float(page.mediabox.height))
            page.merge_page(overlay)
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return ContentFile(output.read(), name=f"preview_{request.id}.pdf")


def create_decline_summary_page(request: SignatureRequest):
    from pypdf import PdfReader
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    declined = request.recipients.filter(decision=SignatureRecipient.DECISION_DISAGREE).order_by("student_name")
    if not declined.exists():
        return None

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    width, height = A4
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(32, y, "비동의 사유 요약")
    y -= 24
    c.setFont("Helvetica", 9)
    c.drawString(32, y, f"Request ID: {request.request_id}")
    y -= 22

    for idx, recipient in enumerate(declined, start=1):
        if y < 70:
            c.showPage()
            y = height - 40
            c.setFont("Helvetica-Bold", 14)
            c.drawString(32, y, "비동의 사유 요약 (계속)")
            y -= 24
            c.setFont("Helvetica", 9)
        line = f"{idx}. {recipient.student_name} / {recipient.parent_name} - {recipient.decline_reason or '(사유 미입력)'}"
        c.drawString(32, y, line[:150])
        y -= 16

    c.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]
