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


def _basename(path: str) -> str:
    return (path or "").replace("\\", "/").split("/")[-1]


def _image_to_pdf_bytes(image_bytes: bytes):
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    image = ImageReader(io.BytesIO(image_bytes))
    width, height = image.getSize()
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(width, height))
    c.drawImage(image, 0, 0, width=width, height=height, preserveAspectRatio=True, mask="auto")
    c.showPage()
    c.save()
    packet.seek(0)
    return packet.read()


def get_document_original_bytes(document: SignatureDocument) -> bytes:
    file_field = document.original_file
    if not file_field:
        raise ValueError("Document file is missing")
    with file_field.open("rb") as f:
        return f.read()


def get_document_pdf_bytes(document: SignatureDocument) -> bytes:
    original_bytes = get_document_original_bytes(document)
    if document.file_type == SignatureDocument.FILE_TYPE_PDF:
        return original_bytes
    return _image_to_pdf_bytes(original_bytes)


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


def _format_size(size: int | None) -> str:
    if size is None:
        return "-"
    return f"{size:,} bytes"


def _build_document_evidence(request: SignatureRequest, original_bytes: bytes) -> dict[str, str]:
    file_name = (request.document_name_snapshot or "").strip()
    if not file_name:
        file_name = _basename(getattr(request.document.original_file, "name", ""))
    file_size = request.document_size_snapshot
    if file_size is None and original_bytes:
        file_size = len(original_bytes)
    sha256 = (request.document_sha256_snapshot or "").strip()
    if not sha256 and original_bytes:
        sha256 = hashlib.sha256(original_bytes).hexdigest()
    return {
        "document_title": request.document.title or "-",
        "document_name": file_name or "-",
        "document_size": _format_size(file_size),
        "document_sha256": sha256 or "-",
    }


def _merge_pdf_bytes(source_pdf_bytes: bytes, summary_pdf_bytes: bytes, *, pdf_title: str = "") -> bytes:
    try:
        from pypdf import PdfReader, PdfWriter
    except ModuleNotFoundError:
        return summary_pdf_bytes

    writer = PdfWriter()
    added_pages = 0
    source_failed = False

    for label, payload in (("source", source_pdf_bytes), ("summary", summary_pdf_bytes)):
        if not payload:
            continue
        try:
            reader = PdfReader(io.BytesIO(payload))
            for page in reader.pages:
                writer.add_page(page)
                added_pages += 1
        except Exception:
            if label == "source":
                source_failed = True
                logger.exception("[consent] source pdf merge skipped")
                continue
            raise

    if added_pages == 0:
        raise ValueError("merged pdf has no pages")
    if source_failed:
        return summary_pdf_bytes

    metadata = {"/Producer": "Eduitit Consent"}
    if (pdf_title or "").strip():
        metadata["/Title"] = pdf_title.strip()
    writer.add_metadata(metadata)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _generate_minimal_summary_pdf(request: SignatureRequest) -> ContentFile:
    def escape_pdf_text(text: str) -> str:
        safe = (text or "").encode("ascii", errors="ignore").decode("ascii")
        return safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines = [
        "Consent Summary",
        f"Request Title: {request.title or '-'}",
        f"Document Title: {request.document.title or '-'}",
        f"Document Name: {(request.document_name_snapshot or _basename(getattr(request.document.original_file, 'name', ''))) or '-'}",
        f"Document SHA256: {(request.document_sha256_snapshot or '-')}",
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


def _build_summary_section_pdf(
    request: SignatureRequest,
    recipients: list[SignatureRecipient],
    evidence: dict[str, str],
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader, simpleSplit
    from reportlab.pdfgen import canvas

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    width, height = A4
    font_name = _resolve_font_name()
    title = request.title or "동의서 수합 결과"
    pdf_title = f"{title} - 동의서 수합 요약"
    c.setTitle(pdf_title)
    c.setAuthor("Eduitit")
    c.setSubject("학부모 동의서 제출 결과")
    now_text = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S")
    created_text = timezone.localtime(request.created_at).strftime("%Y-%m-%d %H:%M:%S")
    sent_text = timezone.localtime(request.sent_at).strftime("%Y-%m-%d %H:%M:%S") if request.sent_at else "-"

    total_count = len(recipients)
    agree_count = sum(1 for r in recipients if r.decision == SignatureRecipient.DECISION_AGREE)
    disagree_count = sum(1 for r in recipients if r.decision == SignatureRecipient.DECISION_DISAGREE)
    responded_count = sum(
        1 for r in recipients if r.status in (SignatureRecipient.STATUS_SIGNED, SignatureRecipient.STATUS_DECLINED)
    )
    pending_count = max(total_count - responded_count, 0)

    def draw_wrapped(label: str, value: str, y: float, *, indent: float = 32, size: int = 9, line_gap: int = 12):
        text = f"{label}: {value or '-'}"
        lines = simpleSplit(text, font_name, size, width - (indent + 24))
        c.setFont(font_name, size)
        for line in lines:
            c.drawString(indent, y, line)
            y -= line_gap
        return y

    def draw_block_title(text: str, y: float):
        c.setFont(font_name, 11)
        c.drawString(32, y, text)
        return y - 14

    y = height - 42
    c.setFont(font_name, 17)
    c.drawString(32, y, "동의서 수합 요약")
    y -= 22

    for label, value in (
        ("동의 요청 제목", title),
        ("안내문 제목", evidence.get("document_title", "-")),
        ("안내문 파일명", evidence.get("document_name", "-")),
        ("안내문 SHA-256", evidence.get("document_sha256", "-")),
        ("안내문 파일크기", evidence.get("document_size", "-")),
        ("요청 ID", str(request.request_id)),
        ("요청 생성 시각", created_text),
        ("최초 발송 시각", sent_text),
        ("요약 생성 시각", now_text),
    ):
        y = draw_wrapped(label, value, y)

    y -= 4
    c.roundRect(30, y - 40, width - 60, 36, 8, stroke=1, fill=0)
    c.setFont(font_name, 9)
    c.drawString(
        40,
        y - 23,
        f"전체 {total_count}명  |  응답 완료 {responded_count}명  |  미응답 {pending_count}명  |  동의 {agree_count}명  |  비동의 {disagree_count}명",
    )
    y -= 56

    y = draw_block_title("발송 안내문(학부모 메시지)", y)
    message_text = (request.message or "").strip() or "-"
    message_lines = []
    for segment in message_text.splitlines() or ["-"]:
        wrapped = simpleSplit(segment, font_name, 9, width - 76)
        message_lines.extend(wrapped or [" "])
    if len(message_lines) > 7:
        message_lines = message_lines[:7]
        if message_lines and message_lines[-1]:
            message_lines[-1] = f"{message_lines[-1][:-1]}…"
    c.setFont(font_name, 9)
    for line in message_lines:
        c.drawString(44, y, line)
        y -= 11

    y -= 2
    y = draw_block_title("개인정보/보관 고지문", y)
    legal_text = (request.legal_notice or "").strip() or "-"
    legal_lines = []
    for segment in legal_text.splitlines() or ["-"]:
        wrapped = simpleSplit(segment, font_name, 9, width - 76)
        legal_lines.extend(wrapped or [" "])
    if len(legal_lines) > 6:
        legal_lines = legal_lines[:6]
        if legal_lines and legal_lines[-1]:
            legal_lines[-1] = f"{legal_lines[-1][:-1]}…"
    c.setFont(font_name, 9)
    for line in legal_lines:
        c.drawString(44, y, line)
        y -= 11

    c.showPage()

    def draw_recipient_header():
        top = height - 40
        c.setFont(font_name, 14)
        c.drawString(32, top, "수신자별 처리 결과")
        c.setFont(font_name, 9)
        c.drawString(32, top - 16, f"요청 ID: {request.request_id}")
        return top - 30

    y = draw_recipient_header()
    if not recipients:
        c.setFont(font_name, 10)
        c.drawString(32, y, "수신자가 없습니다.")
    else:
        block_height = 136
        for idx, recipient in enumerate(recipients, start=1):
            if (y - block_height) < 28:
                c.showPage()
                y = draw_recipient_header()

            c.roundRect(28, y - block_height + 8, width - 56, block_height - 12, 8, stroke=1, fill=0)
            c.setFont(font_name, 10)
            c.drawString(40, y - 12, f"{idx}. 학생: {recipient.student_name} / 보호자: {recipient.parent_name}")
            c.drawString(40, y - 28, f"상태: {_status_label(recipient)}")
            c.drawString(220, y - 28, f"결과: {_decision_label(recipient)}")

            signed_at_text = (
                timezone.localtime(recipient.signed_at).strftime("%Y-%m-%d %H:%M:%S")
                if recipient.signed_at
                else "-"
            )
            c.drawString(40, y - 44, f"처리시각: {signed_at_text}")

            reason = (recipient.decline_reason or "").strip()
            if reason:
                reason_lines = simpleSplit(f"비동의 사유: {reason}", font_name, 9, width - 84)
                c.setFont(font_name, 9)
                for line_idx, line in enumerate(reason_lines[:2]):
                    c.drawString(40, y - 60 - (line_idx * 12), line)

            c.setFont(font_name, 10)
            c.drawString(40, y - 92, "서명")
            sig_box_x = 75
            sig_box_y = y - 114
            sig_box_w = 190
            sig_box_h = 34
            c.rect(sig_box_x, sig_box_y, sig_box_w, sig_box_h, stroke=1, fill=0)

            signature_data = recipient.signature_data or ""
            if signature_data.startswith("data:image"):
                try:
                    image = ImageReader(io.BytesIO(_split_data_url(signature_data)))
                    src_w, src_h = image.getSize()
                    pad = 3.0
                    avail_w = max(sig_box_w - (pad * 2), 1)
                    avail_h = max(sig_box_h - (pad * 2), 1)
                    scale = min(avail_w / src_w, avail_h / src_h)
                    draw_w = src_w * scale
                    draw_h = src_h * scale
                    draw_x = sig_box_x + pad + ((avail_w - draw_w) / 2)
                    draw_y = sig_box_y + pad + ((avail_h - draw_h) / 2)
                    c.drawImage(
                        image,
                        draw_x,
                        draw_y,
                        width=draw_w,
                        height=draw_h,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                except Exception:
                    c.setFont(font_name, 9)
                    c.drawString(sig_box_x + 8, sig_box_y + 13, "서명 이미지 로드 실패")
            else:
                c.setFont(font_name, 9)
                c.drawString(sig_box_x + 8, sig_box_y + 13, "서명 없음")

            y -= block_height

    c.save()
    packet.seek(0)
    return packet.read()


def generate_summary_pdf(request: SignatureRequest) -> ContentFile:
    try:
        # reportlab 불가 시 최소 PDF라도 내려갈 수 있도록 보조 경로 유지.
        import reportlab  # noqa: F401
    except ModuleNotFoundError:
        return _generate_minimal_summary_pdf(request)

    try:
        recipients = list(request.recipients.order_by("student_name", "id"))
        original_bytes = b""
        source_pdf_bytes = b""
        try:
            original_bytes = get_document_original_bytes(request.document)
            source_pdf_bytes = get_document_pdf_bytes(request.document)
        except Exception:
            logger.exception("[consent] source document load failed request_id=%s", request.request_id)

        evidence = _build_document_evidence(request, original_bytes)
        summary_section_bytes = _build_summary_section_pdf(request, recipients, evidence)
        summary_title_seed = (request.title or "").strip()
        if summary_title_seed.lower() in {"untitled", "untitled_document"} or summary_title_seed in {"무제", "제목없음"}:
            summary_title_seed = (request.document.title or "").strip()
        if not summary_title_seed:
            summary_title_seed = "동의서 수합 요약"
        merged_bytes = _merge_pdf_bytes(
            source_pdf_bytes,
            summary_section_bytes,
            pdf_title=f"{summary_title_seed} - 동의서 수합 요약",
        )

        filename = f"summary_{request.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        return ContentFile(merged_bytes, name=filename)
    except Exception:
        logger.exception("[consent] reportlab summary generation failed request_id=%s", request.request_id)
        return _generate_minimal_summary_pdf(request)


def generate_merged_pdf(request: SignatureRequest, include_decline_summary: bool = False) -> ContentFile:
    return generate_summary_pdf(request)
