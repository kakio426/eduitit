from __future__ import annotations

import base64
import hashlib
import io
import os

import requests
from django.conf import settings
from django.core.files.storage import default_storage


PDF_FILE_TYPE = "pdf"
IMAGE_FILE_TYPE = "image"
DOCUMENT_MARK_TYPE_SIGNATURE = "signature"
DOCUMENT_MARK_TYPE_CHECKMARK = "checkmark"


class PdfRuntimeUnavailable(RuntimeError):
    """Raised when PDF generation dependencies are unavailable."""


def ensure_pdf_runtime():
    missing = []
    try:
        import reportlab  # noqa: F401
    except ModuleNotFoundError:
        missing.append("reportlab")
    try:
        import pypdf  # noqa: F401
    except ModuleNotFoundError:
        missing.append("pypdf")
    if missing:
        raise PdfRuntimeUnavailable(f"PDF 엔진 의존성이 누락되었습니다: {', '.join(missing)}")


def get_raw_storage():
    if getattr(settings, "USE_CLOUDINARY", False):
        try:
            from cloudinary_storage.storage import RawMediaCloudinaryStorage

            return RawMediaCloudinaryStorage()
        except (ImportError, Exception):
            return default_storage
    return default_storage


def get_document_storage():
    return default_storage


def basename(path: str) -> str:
    return (path or "").replace("\\", "/").split("/")[-1]


def guess_file_type(filename: str) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return PDF_FILE_TYPE
    return IMAGE_FILE_TYPE


def split_data_url(data_url: str) -> bytes:
    value = (data_url or "").strip()
    if not value.startswith("data:image") or "," not in value:
        raise ValueError("Invalid signature data URL")
    _, payload = value.split(",", 1)
    return base64.b64decode(payload)


def clean_signature_data_url(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized.startswith("data:image") or "," not in normalized:
        raise ValueError("서명 이미지를 다시 입력해 주세요.")
    return normalized


def snapshot_file_metadata(file_obj):
    if not file_obj:
        return "", None, ""

    name = basename(getattr(file_obj, "name", ""))
    if len(name) > 255:
        root, ext = os.path.splitext(name)
        name = f"{root[:240]}{ext}"[:255]

    size = getattr(file_obj, "size", None)
    digest = hashlib.sha256()

    try:
        file_obj.seek(0)
    except Exception:
        pass

    chunks = file_obj.chunks() if hasattr(file_obj, "chunks") else [file_obj.read()]
    for chunk in chunks:
        if chunk:
            digest.update(chunk)

    try:
        file_obj.seek(0)
    except Exception:
        pass

    return name, size, digest.hexdigest()


def _resolve_file_type(file_field, *, file_type: str = "", filename_hint: str = "") -> str:
    return (file_type or guess_file_type(filename_hint or getattr(file_field, "name", ""))).lower()


def _is_cloudinary_file_field(file_field) -> bool:
    storage_module = getattr(getattr(file_field, "storage", None), "__class__", type("X", (), {})).__module__
    if "cloudinary" in (storage_module or "").lower():
        return True
    try:
        return "res.cloudinary.com" in (file_field.url or "")
    except Exception:
        return False


def _cloudinary_private_download_urls(file_field, *, file_type: str = "", filename_hint: str = "") -> list[str]:
    if not getattr(settings, "USE_CLOUDINARY", False):
        return []

    public_id = (getattr(file_field, "name", "") or "").lstrip("/")
    if not public_id:
        return []

    try:
        from cloudinary.utils import private_download_url
    except Exception:
        return []

    normalized_type = _resolve_file_type(file_field, file_type=file_type, filename_hint=filename_hint)
    requested_format = "pdf" if normalized_type == PDF_FILE_TYPE else ""
    urls = []
    seen = set()
    for resource_type in ("image", "raw"):
        try:
            url = private_download_url(
                public_id,
                requested_format,
                resource_type=resource_type,
                type="upload",
            )
        except Exception:
            continue
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def get_file_field_bytes(file_field, *, file_type: str = "", filename_hint: str = "") -> bytes:
    if not file_field:
        raise ValueError("File is missing")
    try:
        with file_field.open("rb") as handle:
            return handle.read()
    except Exception as open_exc:
        if not _is_cloudinary_file_field(file_field):
            raise

        last_download_exc = None
        for url in _cloudinary_private_download_urls(
            file_field,
            file_type=file_type,
            filename_hint=filename_hint,
        ):
            response = None
            try:
                response = requests.get(url, timeout=(5, 30))
                response.raise_for_status()
                return response.content
            except requests.RequestException as download_exc:
                last_download_exc = download_exc
            finally:
                if response is not None:
                    response.close()

        if last_download_exc is not None:
            raise last_download_exc from open_exc
        raise


def _image_to_pdf_bytes(image_bytes: bytes) -> bytes:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    image = ImageReader(io.BytesIO(image_bytes))
    width, height = image.getSize()
    packet = io.BytesIO()
    pdf = canvas.Canvas(packet, pagesize=(width, height))
    pdf.drawImage(image, 0, 0, width=width, height=height, preserveAspectRatio=True, mask="auto")
    pdf.showPage()
    pdf.save()
    packet.seek(0)
    return packet.read()


def get_pdf_bytes_from_file_field(file_field, *, file_type: str = "", filename_hint: str = "") -> bytes:
    normalized_type = _resolve_file_type(file_field, file_type=file_type, filename_hint=filename_hint)
    original_bytes = get_file_field_bytes(
        file_field,
        file_type=normalized_type,
        filename_hint=filename_hint,
    )
    if normalized_type == PDF_FILE_TYPE:
        return original_bytes
    ensure_pdf_runtime()
    return _image_to_pdf_bytes(original_bytes)


def get_pdf_page_sizes(source_pdf_bytes: bytes) -> list[tuple[float, float]]:
    ensure_pdf_runtime()
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(source_pdf_bytes))
    return [
        (float(page.mediabox.width), float(page.mediabox.height))
        for page in reader.pages
    ]


def normalize_pdf_bytes(source_pdf_bytes: bytes) -> bytes:
    ensure_pdf_runtime()
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(source_pdf_bytes))
    if not reader.pages:
        return source_pdf_bytes

    writer = PdfWriter()
    changed = False

    for page in reader.pages:
        rotation = int(getattr(page, "rotation", 0) or 0) % 360
        if rotation:
            page.transfer_rotation_to_content()
            changed = True
        writer.add_page(page)

    if not changed:
        return source_pdf_bytes

    metadata = {}
    if reader.metadata:
        metadata = {key: value for key, value in reader.metadata.items() if value is not None}
        if metadata:
            writer.add_metadata(metadata)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def get_signature_image_bytes(signature_data: str) -> bytes:
    image_bytes = split_data_url(signature_data)
    try:
        from PIL import Image
    except ModuleNotFoundError:
        return image_bytes

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            rgba = image.convert("RGBA")
            alpha = rgba.getchannel("A")
            bbox = alpha.getbbox()
            if not bbox:
                return image_bytes

            pad = 8
            left = max(bbox[0] - pad, 0)
            top = max(bbox[1] - pad, 0)
            right = min(bbox[2] + pad, rgba.width)
            bottom = min(bbox[3] + pad, rgba.height)
            cropped = rgba.crop((left, top, right, bottom))

            output = io.BytesIO()
            cropped.save(output, format="PNG")
            return output.getvalue()
    except Exception:
        return image_bytes


def draw_signature_image(pdf_canvas, signature_data: str, *, x: float, y: float, width: float, height: float):
    from reportlab.lib.utils import ImageReader

    image = ImageReader(io.BytesIO(get_signature_image_bytes(signature_data)))
    src_width, src_height = image.getSize()
    padding = 4.0
    available_width = max(width - (padding * 2), 1.0)
    available_height = max(height - (padding * 2), 1.0)
    scale = min(available_width / src_width, available_height / src_height)
    draw_width = src_width * scale
    draw_height = src_height * scale
    draw_x = x + padding + ((available_width - draw_width) / 2)
    draw_y = y + padding + ((available_height - draw_height) / 2)

    clip_path = pdf_canvas.beginPath()
    clip_path.rect(x + padding, y + padding, available_width, available_height)
    pdf_canvas.saveState()
    pdf_canvas.clipPath(clip_path, stroke=0, fill=0)
    pdf_canvas.drawImage(
        image,
        draw_x,
        draw_y,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf_canvas.restoreState()


def draw_checkmark(pdf_canvas, *, x: float, y: float, width: float, height: float):
    pdf_canvas.saveState()
    pdf_canvas.setStrokeColorRGB(0, 0, 0)
    pdf_canvas.setLineWidth(max(min(width, height) * 0.125, 4.0))
    pdf_canvas.setLineCap(1)
    pdf_canvas.setLineJoin(1)

    start_x = x + (width * 0.25)
    start_y = y + (height * 0.45)
    mid_x = x + (width * 0.45)
    mid_y = y + (height * 0.20)
    end_x = x + (width * 0.80)
    end_y = y + (height * 0.75)

    path = pdf_canvas.beginPath()
    path.moveTo(start_x, start_y)
    path.lineTo(mid_x, mid_y)
    path.lineTo(end_x, end_y)
    pdf_canvas.drawPath(path, stroke=1, fill=0)
    pdf_canvas.restoreState()


def _build_mark_overlay_pdf_bytes(
    *,
    page_width: float,
    page_height: float,
    x: float,
    y: float,
    width: float,
    height: float,
    signature_data: str,
    mark_type: str,
) -> bytes:
    from reportlab.pdfgen import canvas

    packet = io.BytesIO()
    pdf = canvas.Canvas(packet, pagesize=(page_width, page_height))
    if mark_type == DOCUMENT_MARK_TYPE_CHECKMARK:
        draw_checkmark(pdf, x=x, y=y, width=width, height=height)
    else:
        draw_signature_image(pdf, signature_data, x=x, y=y, width=width, height=height)
    pdf.showPage()
    pdf.save()
    packet.seek(0)
    return packet.read()


def build_signed_pdf_bytes(
    source_pdf_bytes: bytes,
    *,
    page_number: int,
    x: float,
    y: float,
    width: float,
    height: float,
    signature_data: str,
    mark_type: str = DOCUMENT_MARK_TYPE_SIGNATURE,
    pdf_title: str = "",
) -> bytes:
    ensure_pdf_runtime()
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(source_pdf_bytes))
    if page_number < 1 or page_number > len(reader.pages):
        raise ValueError("서명 페이지가 문서 범위를 벗어났습니다.")

    target_page = reader.pages[page_number - 1]
    if mark_type not in {DOCUMENT_MARK_TYPE_SIGNATURE, DOCUMENT_MARK_TYPE_CHECKMARK}:
        raise ValueError("지원하지 않는 표시 방식입니다.")
    if mark_type == DOCUMENT_MARK_TYPE_SIGNATURE and not (signature_data or "").strip():
        raise ValueError("서명 이미지가 없습니다.")

    overlay_bytes = _build_mark_overlay_pdf_bytes(
        page_width=float(target_page.mediabox.width),
        page_height=float(target_page.mediabox.height),
        x=x,
        y=y,
        width=width,
        height=height,
        signature_data=signature_data,
        mark_type=mark_type,
    )
    overlay_reader = PdfReader(io.BytesIO(overlay_bytes))

    writer = PdfWriter()
    for index, page in enumerate(reader.pages, start=1):
        if index == page_number:
            page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)

    metadata = {"/Producer": "Eduitit Docsign"}
    if (pdf_title or "").strip():
        metadata["/Title"] = pdf_title.strip()
    writer.add_metadata(metadata)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
