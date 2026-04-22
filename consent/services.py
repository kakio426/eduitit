import hashlib
import io
import logging
from datetime import datetime

from django.core.files.base import ContentFile
from django.utils import timezone

from core.document_signing import (
    DOCUMENT_MARK_TYPE_CHECKMARK,
    DOCUMENT_MARK_TYPE_NAME,
    DOCUMENT_MARK_TYPE_SIGNATURE,
    PdfRuntimeUnavailable,
    basename as _basename,
    build_signed_pdf_bytes,
    ensure_pdf_runtime as _ensure_pdf_runtime,
    get_file_field_bytes,
    get_pdf_bytes_from_file_field,
    guess_file_type,
    normalize_pdf_bytes,
    split_data_url as _split_data_url,
)

from .models import SignatureDocument, SignaturePosition, SignatureRecipient, SignatureRequest

logger = logging.getLogger(__name__)


def get_document_original_bytes(document: SignatureDocument) -> bytes:
    return get_file_field_bytes(document.original_file, file_type=document.file_type)


def get_document_pdf_bytes(document: SignatureDocument) -> bytes:
    return get_pdf_bytes_from_file_field(document.original_file, file_type=document.file_type)


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


def _resolved_signer_name(recipient: SignatureRecipient) -> str:
    override_name = (recipient.signer_name_override or "").strip()
    if override_name:
        return override_name
    if recipient.request.is_guardian_audience:
        return (recipient.parent_name or recipient.student_name or "").strip()
    return (recipient.display_name or recipient.student_name or recipient.parent_name or "").strip()


def _resolve_position_text(position: SignaturePosition, recipient: SignatureRecipient) -> str:
    if position.text_source == SignaturePosition.TEXT_SOURCE_STUDENT_NAME:
        return (recipient.student_name or recipient.display_name or "").strip()
    return _resolved_signer_name(recipient)


def _position_applies_to_decision(position: SignaturePosition, recipient: SignatureRecipient) -> bool:
    if position.check_rule == SignaturePosition.CHECK_RULE_ALWAYS:
        return True
    if position.check_rule == SignaturePosition.CHECK_RULE_DISAGREE:
        return recipient.decision == SignatureRecipient.DECISION_DISAGREE
    return recipient.decision == SignatureRecipient.DECISION_AGREE


def _build_resolved_overlay_marks(recipient: SignatureRecipient) -> list[dict]:
    resolved = []
    for position in recipient.request.configured_positions:
        mark = {
            "page": position.page,
            "x": position.x,
            "y": position.y,
            "width": position.width,
            "height": position.height,
        }
        if position.mark_type == SignaturePosition.MARK_TYPE_NAME:
            text_value = _resolve_position_text(position, recipient)
            if not text_value:
                continue
            resolved.append(
                {
                    **mark,
                    "mark_type": DOCUMENT_MARK_TYPE_NAME,
                    "text_value": text_value,
                }
            )
        elif position.mark_type == SignaturePosition.MARK_TYPE_CHECKMARK:
            if _position_applies_to_decision(position, recipient):
                resolved.append(
                    {
                        **mark,
                        "mark_type": DOCUMENT_MARK_TYPE_CHECKMARK,
                    }
                )
        else:
            resolved.append(
                {
                    **mark,
                    "mark_type": DOCUMENT_MARK_TYPE_SIGNATURE,
                }
            )
    return resolved


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


def _wrap_pdf_lines(text: str, font_name: str, size: int, max_width: float, *, max_lines: int | None = None) -> list[str]:
    from reportlab.lib.utils import simpleSplit

    raw_text = (text or "").strip() or "-"
    lines = []
    for segment in raw_text.splitlines() or [raw_text]:
        wrapped = simpleSplit(segment or " ", font_name, size, max_width)
        lines.extend(wrapped or [" "])
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = (lines[-1] or "").rstrip()
        lines[-1] = f"{last[:-1]}…" if len(last) > 1 else "…"
    return lines



def _draw_pdf_lines(c, lines: list[str], x: float, y: float, *, font_name: str, size: int, line_gap: int) -> float:
    c.setFont(font_name, size)
    for line in lines:
        c.drawString(x, y, line)
        y -= line_gap
    return y



def _draw_signature_preview(
    c,
    signature_data: str,
    *,
    box_x: float,
    box_y: float,
    box_w: float,
    box_h: float,
    font_name: str,
):
    from reportlab.lib.utils import ImageReader

    c.roundRect(box_x, box_y, box_w, box_h, 6, stroke=1, fill=0)
    if signature_data.startswith("data:image"):
        try:
            image = ImageReader(io.BytesIO(_split_data_url(signature_data)))
            src_w, src_h = image.getSize()
            pad = 4.0
            avail_w = max(box_w - (pad * 2), 1)
            avail_h = max(box_h - (pad * 2), 1)
            scale = min(avail_w / src_w, avail_h / src_h)
            draw_w = src_w * scale
            draw_h = src_h * scale
            draw_x = box_x + pad + ((avail_w - draw_w) / 2)
            draw_y = box_y + pad + ((avail_h - draw_h) / 2)
            clip_path = c.beginPath()
            clip_path.rect(box_x + pad, box_y + pad, avail_w, avail_h)
            c.saveState()
            c.clipPath(clip_path, stroke=0, fill=0)
            c.drawImage(
                image,
                draw_x,
                draw_y,
                width=draw_w,
                height=draw_h,
                preserveAspectRatio=True,
                mask="auto",
            )
            c.restoreState()
            return
        except Exception:
            fallback_text = "서명 이미지 로드 실패"
    else:
        fallback_text = "서명 없음"

    c.setFont(font_name, 9)
    c.drawCentredString(box_x + (box_w / 2), box_y + (box_h / 2) - 3, fallback_text)


def _merge_pdf_bytes(
    source_pdf_bytes: bytes,
    summary_pdf_bytes: bytes,
    *,
    pdf_title: str = "",
    source_page_limit: int | None = None,
) -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    added_pages = 0
    source_failed = False

    def add_pages(payload: bytes, *, limit: int | None = None):
        nonlocal added_pages
        reader = PdfReader(io.BytesIO(payload))
        for index, page in enumerate(reader.pages):
            if limit is not None and index >= limit:
                break
            writer.add_page(page)
            added_pages += 1

    if source_pdf_bytes:
        try:
            add_pages(source_pdf_bytes, limit=source_page_limit)
        except Exception:
            source_failed = True
            logger.exception("[consent] source pdf merge skipped")

    if summary_pdf_bytes:
        add_pages(summary_pdf_bytes)

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
    from reportlab.lib.utils import simpleSplit
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
        header_gap = 12
        meta_gap = 13
        reason_gap = 11
        signature_label_x = 40
        signature_box_x = 78
        signature_box_w = width - 124
        signature_box_h = 42

        for idx, recipient in enumerate(recipients, start=1):
            header_lines = _wrap_pdf_lines(
                f"{idx}. 학생: {recipient.student_name} / 보호자: {recipient.parent_name}",
                font_name,
                10,
                width - 84,
                max_lines=2,
            )
            reason = (recipient.decline_reason or "").strip()
            reason_lines = (
                _wrap_pdf_lines(f"비동의 사유: {reason}", font_name, 9, width - 92, max_lines=4)
                if reason
                else []
            )
            block_height = 34 + (len(header_lines) * header_gap) + (2 * meta_gap) + (len(reason_lines) * reason_gap) + 18 + signature_box_h + 18
            block_height = max(block_height, 148)
            if (y - block_height) < 28:
                c.showPage()
                y = draw_recipient_header()

            box_bottom = y - block_height + 8
            c.roundRect(28, box_bottom, width - 56, block_height - 12, 8, stroke=1, fill=0)

            cursor_y = y - 18
            cursor_y = _draw_pdf_lines(
                c,
                header_lines,
                40,
                cursor_y,
                font_name=font_name,
                size=10,
                line_gap=header_gap,
            )
            c.setFont(font_name, 9)
            c.drawString(40, cursor_y, f"상태: {_status_label(recipient)}")
            c.drawString(220, cursor_y, f"결과: {_decision_label(recipient)}")
            cursor_y -= meta_gap

            signed_at_text = (
                timezone.localtime(recipient.signed_at).strftime("%Y-%m-%d %H:%M:%S")
                if recipient.signed_at
                else "-"
            )
            c.drawString(40, cursor_y, f"처리시각: {signed_at_text}")
            c.drawString(220, cursor_y, f"증빙수준: {_identity_assurance_label(recipient)}")
            cursor_y -= meta_gap

            if reason_lines:
                cursor_y = _draw_pdf_lines(
                    c,
                    reason_lines,
                    40,
                    cursor_y,
                    font_name=font_name,
                    size=9,
                    line_gap=reason_gap,
                )

            c.setFont(font_name, 10)
            c.drawString(signature_label_x, box_bottom + signature_box_h + 20, "서명")
            _draw_signature_preview(
                c,
                recipient.signature_data or "",
                box_x=signature_box_x,
                box_y=box_bottom + 14,
                box_w=signature_box_w,
                box_h=signature_box_h,
                font_name=font_name,
            )

            y -= block_height

    c.save()
    packet.seek(0)
    return packet.read()


def generate_summary_pdf(request: SignatureRequest) -> ContentFile:
    _ensure_pdf_runtime()

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
            source_page_limit=1,
        )

        filename = f"summary_{request.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        return ContentFile(merged_bytes, name=filename)
    except Exception:
        logger.exception("[consent] reportlab summary generation failed request_id=%s", request.request_id)
        raise


def _identity_assurance_label(recipient: SignatureRecipient) -> str:
    if recipient.identity_assurance == SignatureRecipient.IDENTITY_PHONE_LAST4:
        return "전화번호 끝 4자리 확인"
    return "링크 기반 제출"


def _format_dt(value) -> str:
    if not value:
        return "-"
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")


def _truncate_text(value: str, limit: int = 220) -> str:
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"


def _build_recipient_evidence_section_pdf(
    recipient: SignatureRecipient,
    evidence: dict[str, str],
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    request = recipient.request
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    width, height = A4
    font_name = _resolve_font_name()
    pdf_title_seed = (request.title or request.document.title or "동의서 증빙").strip() or "동의서 증빙"
    c.setTitle(f"{pdf_title_seed} - {recipient.student_name} 증빙")
    c.setAuthor("Eduitit")
    c.setSubject("동의서 개별 제출 증빙")

    def draw_wrapped(label: str, value: str, y: float, *, indent: float = 34, size: int = 9, line_gap: int = 12):
        lines = _wrap_pdf_lines(f"{label}: {value or '-'}", font_name, size, width - (indent + 28))
        return _draw_pdf_lines(c, lines, indent, y, font_name=font_name, size=size, line_gap=line_gap)

    def draw_block_title(text: str, y: float):
        c.setFont(font_name, 11)
        c.drawString(32, y, text)
        return y - 14

    def start_continued_page(title_text: str) -> float:
        c.showPage()
        top = height - 40
        c.setFont(font_name, 15)
        c.drawString(32, top, title_text)
        c.setFont(font_name, 9)
        c.drawString(32, top - 16, f"요청 ID: {request.request_id}")
        return top - 30

    y = height - 40
    c.setFont(font_name, 17)
    c.drawString(32, y, "개별 제출 증빙")
    y -= 24

    for label, value in (
        ("요청 ID", str(request.request_id)),
        ("동의 요청 제목", request.title or "-"),
        ("안내문 제목", request.document.title or "-"),
        ("안내문 파일명", evidence.get("document_name", "-")),
        ("안내문 SHA-256", evidence.get("document_sha256", "-")),
        ("안내문 파일크기", evidence.get("document_size", "-")),
        ("학생명", recipient.student_name or "-"),
        ("보호자명", recipient.parent_name or "-"),
        ("서명자명", _resolved_signer_name(recipient) or "-"),
        ("증빙 수준", _identity_assurance_label(recipient)),
        ("본인확인 시각", _format_dt(recipient.verified_at)),
        ("본인확인 IP", recipient.verified_ip_address or "-"),
        ("제출 시각", _format_dt(recipient.signed_at)),
        ("제출 IP", recipient.ip_address or "-"),
        ("제출 브라우저", _truncate_text(recipient.user_agent, limit=180) or "-"),
        ("처리 상태", _status_label(recipient)),
        ("동의 결과", _decision_label(recipient)),
    ):
        y = draw_wrapped(label, value, y)

    reason = (recipient.decline_reason or "").strip()
    reason_lines = _wrap_pdf_lines(reason, font_name, 9, width - 76, max_lines=6) if reason else []
    signature_box_h = 112
    required_height = (18 + (len(reason_lines) * 11) if reason_lines else 0) + 22 + signature_box_h + 34
    if (y - required_height) < 48:
        y = start_continued_page("개별 제출 증빙 (서명)")

    if reason_lines:
        y -= 2
        y = draw_block_title("비동의 사유", y)
        y = _draw_pdf_lines(c, reason_lines, 44, y, font_name=font_name, size=9, line_gap=11)

    y -= 4
    y = draw_block_title("서명 이미지", y)
    sig_box_y = y - signature_box_h - 4
    _draw_signature_preview(
        c,
        recipient.signature_data or "",
        box_x=42,
        box_y=sig_box_y,
        box_w=width - 84,
        box_h=signature_box_h,
        font_name=font_name,
    )

    footer_y = 34
    c.setFont(font_name, 8)
    c.drawString(32, footer_y, f"생성 시각: {_format_dt(timezone.now())}")
    c.drawRightString(width - 32, footer_y, "Eduitit Consent Evidence")

    c.save()
    packet.seek(0)
    return packet.read()


def _build_resolved_source_pdf_bytes(
    recipient: SignatureRecipient,
    *,
    source_pdf_bytes: bytes,
    pdf_title: str = "",
) -> bytes:
    if not source_pdf_bytes:
        return b""

    overlay_marks = _build_resolved_overlay_marks(recipient)
    if not overlay_marks:
        return source_pdf_bytes

    signature_data = recipient.signature_data or ""
    if not any(mark["mark_type"] == DOCUMENT_MARK_TYPE_SIGNATURE for mark in overlay_marks):
        signature_data = ""

    return build_signed_pdf_bytes(
        source_pdf_bytes,
        marks=overlay_marks,
        signature_data=signature_data,
        pdf_title=pdf_title,
    )


def generate_recipient_evidence_pdf(recipient: SignatureRecipient) -> ContentFile:
    _ensure_pdf_runtime()

    request = recipient.request
    try:
        original_bytes = b""
        source_pdf_bytes = b""
        try:
            original_bytes = get_document_original_bytes(request.document)
            source_pdf_bytes = normalize_pdf_bytes(get_document_pdf_bytes(request.document))
        except Exception:
            logger.exception("[consent] recipient evidence source load failed request_id=%s recipient_id=%s", request.request_id, recipient.id)

        evidence = _build_document_evidence(request, original_bytes)
        evidence_section_bytes = _build_recipient_evidence_section_pdf(recipient, evidence)
        title_seed = (request.title or request.document.title or "동의서 제출 증빙").strip() or "동의서 제출 증빙"
        resolved_source_bytes = _build_resolved_source_pdf_bytes(
            recipient,
            source_pdf_bytes=source_pdf_bytes,
            pdf_title=f"{title_seed} - 제출본",
        )
        merged_bytes = _merge_pdf_bytes(
            resolved_source_bytes,
            evidence_section_bytes,
            pdf_title=f"{title_seed} - {recipient.student_name} 증빙",
        )
        filename = f"recipient_{request.id}_{recipient.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        return ContentFile(merged_bytes, name=filename)
    except Exception:
        logger.exception(
            "[consent] recipient evidence pdf generation failed request_id=%s recipient_id=%s",
            request.request_id,
            recipient.id,
        )
        raise


def generate_merged_pdf(request: SignatureRequest, include_decline_summary: bool = False) -> ContentFile:
    _ensure_pdf_runtime()
    recipients = list(
        request.recipients.filter(
            status__in=(
                SignatureRecipient.STATUS_SIGNED,
                SignatureRecipient.STATUS_DECLINED,
            )
        ).order_by("student_name", "id")
    )
    if not recipients:
        raise ValueError("merged pdf has no completed recipients")

    try:
        from pypdf import PdfReader, PdfWriter

        original_bytes = b""
        source_pdf_bytes = normalize_pdf_bytes(get_document_pdf_bytes(request.document))
        title_seed = (request.title or request.document.title or "동의서 제출 결과").strip() or "동의서 제출 결과"

        writer = PdfWriter()
        added_pages = 0

        for recipient in recipients:
            recipient_pdf_bytes = _build_resolved_source_pdf_bytes(
                recipient,
                source_pdf_bytes=source_pdf_bytes,
                pdf_title=f"{title_seed} - {recipient.student_name} 제출본",
            )
            recipient_reader = PdfReader(io.BytesIO(recipient_pdf_bytes))
            for page in recipient_reader.pages:
                writer.add_page(page)
                added_pages += 1

        if include_decline_summary:
            try:
                original_bytes = get_document_original_bytes(request.document)
            except Exception:
                logger.exception("[consent] merged pdf summary source load failed request_id=%s", request.request_id)
            evidence = _build_document_evidence(request, original_bytes)
            summary_section_bytes = _build_summary_section_pdf(request, recipients, evidence)
            summary_reader = PdfReader(io.BytesIO(summary_section_bytes))
            for page in summary_reader.pages:
                writer.add_page(page)
                added_pages += 1

        if added_pages == 0:
            raise ValueError("merged pdf has no pages")

        writer.add_metadata(
            {
                "/Producer": "Eduitit Consent",
                "/Title": f"{title_seed} - 완성본",
            }
        )

        output = io.BytesIO()
        writer.write(output)
        filename = f"merged_{request.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        return ContentFile(output.getvalue(), name=filename)
    except ValueError:
        raise
    except Exception:
        logger.exception("[consent] merged pdf generation failed request_id=%s", request.request_id)
        raise
