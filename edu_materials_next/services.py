import base64
import io

import qrcode
from django.core.exceptions import ValidationError

from products.models import Product

SERVICE_ROUTE = "edu_materials_next:main"
SERVICE_TITLE = "AI 자료실 Next"
HTML_MAX_BYTES = 5 * 1024 * 1024
HTML_EXTENSIONS = (".html", ".htm")


def get_service():
    return Product.objects.filter(launch_route_name=SERVICE_ROUTE).first() or Product.objects.filter(
        title=SERVICE_TITLE
    ).first()


def build_material_qr_data_url(raw_text):
    if not raw_text:
        return ""

    qr_image = qrcode.make(raw_text)
    with io.BytesIO() as buffer:
        qr_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def decode_uploaded_html(uploaded_file):
    raw_bytes = uploaded_file.read()
    uploaded_file.seek(0)
    for encoding in ("utf-8-sig", "utf-16", "cp949"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError("자료 파일 글자를 읽지 못했습니다. UTF-8 형식으로 저장한 뒤 다시 올려 주세요.")


def validate_html_upload(uploaded_file):
    if uploaded_file is None:
        raise ValidationError("자료 파일을 선택해 주세요.")
    if uploaded_file.size > HTML_MAX_BYTES:
        raise ValidationError("자료 파일은 최대 5MB까지 올릴 수 있습니다.")
    name = (uploaded_file.name or "").lower()
    if not name.endswith(HTML_EXTENSIONS):
        raise ValidationError("웹자료 파일(.html)만 올릴 수 있습니다.")

    html_content = decode_uploaded_html(uploaded_file)
    if not html_content.strip():
        raise ValidationError("비어 있는 자료 파일은 저장할 수 없습니다.")

    return {
        "html_content": html_content,
        "original_filename": uploaded_file.name or "",
    }

