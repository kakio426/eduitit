import logging
import mimetypes
import os
import tempfile
from pathlib import Path
from threading import Lock
from time import monotonic

from products.models import Product

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - optional dependency
    genai = None
    genai_types = None


logger = logging.getLogger(__name__)

SERVICE_ROUTE = "ocrdesk:main"
SERVICE_TITLE = "사진 글자 읽기"
GEMINI_OCR_MODEL_NAME = "gemini-2.5-flash-lite"
_GEMINI_OCR_PROMPT = (
    "이미지에서 보이는 글자만 그대로 추출하세요.\n"
    "설명, 요약, 번역, 마크다운 없이 텍스트만 출력하세요.\n"
    "줄바꿈은 가능한 한 원본과 비슷하게 유지하고, 보이지 않는 내용은 추측하지 마세요."
)

_OCR_ENGINE = None
_OCR_INIT_ERROR = None
_OCR_LAST_INIT_ATTEMPT_AT = 0.0
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


def _get_init_retry_cooldown_seconds():
    raw_value = os.environ.get("OCRDESK_ENGINE_RETRY_COOLDOWN_SECONDS", "15")
    try:
        cooldown_seconds = float(raw_value)
    except (TypeError, ValueError):
        return 15.0
    return max(0.0, cooldown_seconds)


def _get_cpu_threads():
    raw_value = os.environ.get("OCRDESK_CPU_THREADS", "2")
    try:
        cpu_threads = int(raw_value)
    except (TypeError, ValueError):
        return 2
    return max(1, cpu_threads)


def _get_paddlex_cache_dir():
    configured_dir = os.environ.get("OCRDESK_PADDLE_CACHE_HOME") or os.environ.get("PADDLE_PDX_CACHE_HOME")
    cache_dir = Path(configured_dir) if configured_dir else Path(tempfile.gettempdir()) / "ocrdesk" / "paddlex"
    cache_dir = cache_dir.expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return str(cache_dir)


def _get_gemini_api_key():
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _get_gemini_model_name():
    return os.environ.get("OCRDESK_GEMINI_MODEL", GEMINI_OCR_MODEL_NAME).strip() or GEMINI_OCR_MODEL_NAME


def _is_retry_cooldown_active(now):
    if _OCR_INIT_ERROR is None:
        return False
    return (now - _OCR_LAST_INIT_ATTEMPT_AT) < _get_init_retry_cooldown_seconds()


def reset_ocr_engine_state():
    global _OCR_ENGINE, _OCR_INIT_ERROR, _OCR_LAST_INIT_ATTEMPT_AT

    _OCR_ENGINE = None
    _OCR_INIT_ERROR = None
    _OCR_LAST_INIT_ATTEMPT_AT = 0.0


def _build_engine():
    cache_dir = _get_paddlex_cache_dir()
    os.environ["PADDLE_PDX_CACHE_HOME"] = cache_dir
    os.environ.setdefault("PADDLE_HOME", cache_dir)
    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

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
        enable_mkldnn=False,
        enable_cinn=False,
        cpu_threads=_get_cpu_threads(),
    )


def get_ocr_engine():
    global _OCR_ENGINE, _OCR_INIT_ERROR, _OCR_LAST_INIT_ATTEMPT_AT

    if _OCR_ENGINE is not None:
        return _OCR_ENGINE

    now = monotonic()
    if _is_retry_cooldown_active(now):
        raise OCREngineUnavailable("ocr_engine_not_ready") from _OCR_INIT_ERROR

    with _OCR_LOCK:
        if _OCR_ENGINE is not None:
            return _OCR_ENGINE

        now = monotonic()
        if _is_retry_cooldown_active(now):
            raise OCREngineUnavailable("ocr_engine_not_ready") from _OCR_INIT_ERROR

        _OCR_LAST_INIT_ATTEMPT_AT = now
        try:
            _OCR_ENGINE = _build_engine()
            _OCR_INIT_ERROR = None
        except Exception as exc:
            _OCR_ENGINE = None
            _OCR_INIT_ERROR = exc
            logger.exception("[ocrdesk] OCR engine initialization failed")
            raise OCREngineUnavailable("ocr_engine_not_ready") from exc
        return _OCR_ENGINE


def _normalize_text(value):
    text = " ".join(str(value or "").split())
    return text.strip()


def _join_normalized_lines(lines):
    normalized_lines = []
    for raw_line in lines:
        line = _normalize_text(raw_line)
        if not line:
            continue
        if normalized_lines and normalized_lines[-1] == line:
            continue
        normalized_lines.append(line)
    return "\n".join(normalized_lines).strip()


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


def _read_temp_file_bytes(temp_path):
    with open(temp_path, "rb") as temp_file:
        return temp_file.read()


def _get_mime_type(uploaded_file, temp_path):
    content_type = (getattr(uploaded_file, "content_type", "") or "").strip()
    if content_type:
        return content_type
    guessed_type, _ = mimetypes.guess_type(temp_path)
    return guessed_type or "image/png"


def _extract_text_with_gemini(uploaded_file, temp_path):
    api_key = _get_gemini_api_key()
    if not api_key or genai is None or genai_types is None:
        return None

    try:
        image_bytes = _read_temp_file_bytes(temp_path)
        mime_type = _get_mime_type(uploaded_file, temp_path)
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=_get_gemini_model_name(),
            contents=[
                _GEMINI_OCR_PROMPT,
                genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            ],
        )
        return _join_normalized_lines((getattr(response, "text", "") or "").splitlines())
    except Exception:
        logger.exception("[ocrdesk] Gemini OCR fallback failed")
        return None


def extract_text_from_upload(uploaded_file):
    temp_path = _write_temp_upload(uploaded_file)
    try:
        try:
            engine = get_ocr_engine()
            result = engine.predict(input=temp_path)
        except OCREngineUnavailable:
            fallback_text = _extract_text_with_gemini(uploaded_file, temp_path)
            if fallback_text is not None:
                logger.warning("[ocrdesk] Paddle OCR engine unavailable; served Gemini OCR fallback instead")
                return fallback_text
            raise
        except Exception as exc:
            logger.warning("[ocrdesk] OCR prediction failed; attempting Gemini fallback", exc_info=True)
            fallback_text = _extract_text_with_gemini(uploaded_file, temp_path)
            if fallback_text is not None:
                logger.warning("[ocrdesk] Paddle OCR prediction failed; served Gemini OCR fallback instead")
                return fallback_text
            raise OCRProcessingError("ocr_prediction_failed") from exc

        fragments = _extract_text_fragments(result)
        return _join_normalized_lines(fragments)
    except Exception as exc:
        if isinstance(exc, (OCREngineUnavailable, OCRProcessingError)):
            raise
        logger.exception("[ocrdesk] OCR prediction failed")
        raise OCRProcessingError("ocr_prediction_failed") from exc
    finally:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("[ocrdesk] failed to remove temp file: %s", temp_path, exc_info=True)
