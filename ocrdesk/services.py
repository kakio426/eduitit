import logging
import os
import tempfile
from pathlib import Path
from threading import Lock

from products.models import Product


logger = logging.getLogger(__name__)

SERVICE_ROUTE = "ocrdesk:main"
SERVICE_TITLE = "사진 글자 읽기"

_OCR_ENGINE = None
_OCR_INIT_ERROR = None
_OCR_LOCK = Lock()
_TEXT_LIST_KEYS = {"rec_texts", "texts"}
_TEXT_VALUE_KEYS = {"rec_text", "text"}
_IGNORED_RESULT_KEYS = {
    "input_path",
    "page_index",
    "model_settings",
    "dt_polys",
    "dt_scores",
    "rec_polys",
    "rec_scores",
    "score",
    "scores",
}


class OCREngineUnavailable(Exception):
    pass


class OCRProcessingError(Exception):
    pass


def get_service():
    return Product.objects.filter(launch_route_name=SERVICE_ROUTE).first() or Product.objects.filter(title=SERVICE_TITLE).first()


def _build_engine():
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")

    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise OCREngineUnavailable("paddleocr_import_error") from exc

    return PaddleOCR(
        lang="korean",
        device="cpu",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def get_ocr_engine():
    global _OCR_ENGINE, _OCR_INIT_ERROR

    if _OCR_ENGINE is not None:
        return _OCR_ENGINE
    if _OCR_INIT_ERROR is not None:
        raise OCREngineUnavailable("ocr_engine_not_ready") from _OCR_INIT_ERROR

    with _OCR_LOCK:
        if _OCR_ENGINE is not None:
            return _OCR_ENGINE
        if _OCR_INIT_ERROR is not None:
            raise OCREngineUnavailable("ocr_engine_not_ready") from _OCR_INIT_ERROR
        try:
            _OCR_ENGINE = _build_engine()
        except Exception as exc:
            _OCR_INIT_ERROR = exc
            logger.exception("[ocrdesk] OCR engine initialization failed")
            raise OCREngineUnavailable("ocr_engine_not_ready") from exc
        return _OCR_ENGINE


def _normalize_text(value):
    text = " ".join(str(value or "").split())
    return text.strip()


def _extract_text_fragments(node, *, parent_key=""):
    if node is None:
        return []

    if hasattr(node, "json"):
        json_payload = getattr(node, "json")
        if callable(json_payload):
            try:
                json_payload = json_payload()
            except Exception:
                logger.exception("[ocrdesk] failed to read result.json() payload")
                json_payload = None
        if json_payload is not None:
            return _extract_text_fragments(json_payload)

    if isinstance(node, dict):
        if "res" in node:
            return _extract_text_fragments(node["res"], parent_key="res")

        fragments = []
        for key in _TEXT_LIST_KEYS:
            if key in node:
                fragments.extend(_extract_text_fragments(node[key], parent_key=key))
        for key in _TEXT_VALUE_KEYS:
            if key in node:
                fragments.extend(_extract_text_fragments(node[key], parent_key=key))
        if fragments:
            return fragments

        for key, value in node.items():
            if key in _IGNORED_RESULT_KEYS:
                continue
            fragments.extend(_extract_text_fragments(value, parent_key=key))
        return fragments

    if isinstance(node, (list, tuple)):
        fragments = []
        for item in node:
            fragments.extend(_extract_text_fragments(item, parent_key=parent_key))
        return fragments

    if isinstance(node, str):
        if parent_key in _TEXT_LIST_KEYS or parent_key in _TEXT_VALUE_KEYS:
            normalized = _normalize_text(node)
            return [normalized] if normalized else []
        return []

    return []


def _write_temp_upload(uploaded_file):
    suffix = Path(uploaded_file.name or "").suffix.lower() or ".png"
    temp_handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp_handle.name
    try:
        for chunk in uploaded_file.chunks():
            temp_handle.write(chunk)
    finally:
        temp_handle.close()
    return temp_path


def extract_text_from_upload(uploaded_file):
    engine = get_ocr_engine()
    temp_path = _write_temp_upload(uploaded_file)
    try:
        result = engine.predict(input=temp_path)
        fragments = _extract_text_fragments(result)
        normalized_lines = []
        for fragment in fragments:
            line = _normalize_text(fragment)
            if not line:
                continue
            if normalized_lines and normalized_lines[-1] == line:
                continue
            normalized_lines.append(line)
        return "\n".join(normalized_lines).strip()
    except OCREngineUnavailable:
        raise
    except Exception as exc:
        logger.exception("[ocrdesk] OCR prediction failed")
        raise OCRProcessingError("ocr_prediction_failed") from exc
    finally:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("[ocrdesk] failed to remove temp file: %s", temp_path, exc_info=True)

