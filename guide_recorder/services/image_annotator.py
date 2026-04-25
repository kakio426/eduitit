import io

import cv2
import numpy as np
from PIL import Image, ImageDraw


def annotate(pil_image: Image.Image, norm_x: float, norm_y: float, element_metadata: dict = None) -> Image.Image:
    """
    클릭 좌표 위치에 빨간 원 + 바운딩 박스를 합성한 PIL Image를 반환한다.

    norm_x, norm_y: 0.0~1.0 정규화 좌표 (click_pixel / canvas_dimension)
    element_metadata: {tag, text, id, href, classList} — 박스 크기 계산에 활용
    """
    img = pil_image.convert('RGB')
    w, h = img.size

    abs_x = int(norm_x * w)
    abs_y = int(norm_y * h)

    # --- Pillow: 빨간 바운딩 박스 ---
    box_half = 36  # 기본 박스 반경 (72×72px)
    x1 = max(0, abs_x - box_half)
    y1 = max(0, abs_y - box_half)
    x2 = min(w, abs_x + box_half)
    y2 = min(h, abs_y + box_half)

    draw = ImageDraw.Draw(img)
    for offset in range(3):  # 3px 두께
        draw.rectangle(
            [x1 - offset, y1 - offset, x2 + offset, y2 + offset],
            outline=(220, 38, 38),  # Tailwind red-600
        )

    # --- OpenCV: 안티앨리어싱 빨간 원 ---
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # 흰 테두리 원 (바깥)
    cv2.circle(cv_img, (abs_x, abs_y), 18, (255, 255, 255), 4, cv2.LINE_AA)
    # 빨간 채움 원 (안)
    cv2.circle(cv_img, (abs_x, abs_y), 12, (38, 38, 220), -1, cv2.LINE_AA)  # BGR
    # 흰 중심점
    cv2.circle(cv_img, (abs_x, abs_y), 3, (255, 255, 255), -1, cv2.LINE_AA)

    result = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
    return result


def to_jpeg_bytes(pil_image: Image.Image, quality: int = 82) -> bytes:
    """PIL Image → JPEG bytes (Cloudinary 업로드 전 용량 감소용)."""
    buf = io.BytesIO()
    pil_image.convert('RGB').save(buf, format='JPEG', quality=quality, optimize=True)
    return buf.getvalue()
