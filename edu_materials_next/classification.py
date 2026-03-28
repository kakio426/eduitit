import html
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass

from django.utils.html import strip_tags
from openai import OpenAI

from .models import NextEduMaterial


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"
SUMMARY_MAX_LENGTH = 80
TAG_LIMIT = 5
TEXT_LIMIT = 4000


class NextEduMaterialClassificationError(Exception):
    """Raised when next edu material classification cannot be completed."""


@dataclass(frozen=True)
class MaterialMetadata:
    subject: str
    grade: str
    unit_title: str
    material_type: str
    tags: list[str]
    summary: str
    confidence: float
    visible_text: str
    search_text: str


def extract_visible_text(html_content: str) -> str:
    sanitized = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", str(html_content or ""))
    sanitized = re.sub(r">\s*<", "> <", sanitized)
    text = strip_tags(sanitized)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_tags_input(raw_value: str, *, limit: int = TAG_LIMIT) -> list[str]:
    parts = re.split(r"[\n,#]+", str(raw_value or ""))
    normalized: list[str] = []
    seen = set()
    for part in parts:
        cleaned = re.sub(r"\s+", " ", part).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned[:30])
        if len(normalized) >= limit:
            break
    return normalized


def build_search_text(material: NextEduMaterial, *, visible_text: str = "") -> str:
    text = str(visible_text or "").strip()
    if not text:
        text = extract_visible_text(material.html_content)
    chunks = [
        material.title,
        material.original_filename,
        material.get_subject_display() if material.subject else "",
        material.grade,
        material.unit_title,
        material.get_material_type_display() if material.material_type else "",
        " ".join(material.tags or []),
        material.summary,
        material.teacher_guide,
        " ".join(material.student_questions or []),
        " ".join(material.remix_tips or []),
        text[:TEXT_LIMIT],
    ]
    joined = " ".join(chunk.strip() for chunk in chunks if chunk and chunk.strip())
    return re.sub(r"\s+", " ", joined).strip()


def apply_manual_metadata(
    material: NextEduMaterial,
    *,
    subject: str,
    grade: str,
    unit_title: str,
    material_type: str,
    tags,
    summary: str,
    save: bool = True,
):
    material.subject = _normalize_subject(subject)
    material.grade = str(grade or "").strip()[:50]
    material.unit_title = str(unit_title or "").strip()[:200]
    material.material_type = _normalize_material_type(material_type)
    material.tags = _normalize_tags(tags)
    material.summary = _normalize_summary(summary)
    visible_text = extract_visible_text(material.html_content)
    material.search_text = build_search_text(material, visible_text=visible_text)

    if save:
        material.save(
            update_fields=[
                "subject",
                "grade",
                "unit_title",
                "material_type",
                "tags",
                "summary",
                "search_text",
                "updated_at",
            ]
        )
    return material


def apply_auto_metadata(material: NextEduMaterial, *, save: bool = True, timeout_seconds: int = 12):
    visible_text = extract_visible_text(material.html_content)
    material.search_text = build_search_text(material, visible_text=visible_text)

    try:
        metadata = classify_material(material, visible_text=visible_text, timeout_seconds=timeout_seconds)
    except Exception:
        if save:
            material.save(update_fields=["search_text", "updated_at"])
        return None

    material.subject = metadata.subject
    material.grade = metadata.grade
    material.unit_title = metadata.unit_title
    material.material_type = metadata.material_type
    material.tags = metadata.tags
    material.summary = metadata.summary
    material.search_text = metadata.search_text

    if save:
        material.save(
            update_fields=[
                "subject",
                "grade",
                "unit_title",
                "material_type",
                "tags",
                "summary",
                "search_text",
                "updated_at",
            ]
        )
    return metadata


def classify_material(material: NextEduMaterial, *, visible_text: str = "", timeout_seconds: int = 12) -> MaterialMetadata:
    text = str(visible_text or "").strip() or extract_visible_text(material.html_content)
    payload = {
        "title": str(material.title or "").strip(),
        "original_filename": str(material.original_filename or "").strip(),
        "entry_mode": str(material.entry_mode or "").strip(),
        "visible_text_excerpt": text[:TEXT_LIMIT],
    }
    prompt = (
        "당신은 교사용 AI 자료실 Next의 자동 분류기입니다. "
        "반드시 JSON 객체만 반환하세요. "
        "subject는 KOREAN, MATH, SOCIAL, SCIENCE, OTHER 중 하나여야 합니다. "
        "material_type은 intro, exploration, practice, quiz, game, reference, presentation, tool, other 중 하나여야 합니다. "
        "grade는 50자 이하, unit_title은 200자 이하, tags는 3~5개 문자열 배열, summary는 80자 이하 한 문장, confidence는 0과 1 사이 숫자만 사용하세요. "
        "자료를 다시 찾기 쉽게 분류하고, 과장하지 말고 제목과 본문에서 확인 가능한 정보만 사용하세요."
    )
    response = _call_json_response(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        timeout_seconds=timeout_seconds,
    )

    subject = _normalize_subject(response.get("subject"))
    grade = str(response.get("grade") or "").strip()[:50]
    unit_title = str(response.get("unit_title") or "").strip()[:200]
    material_type = _normalize_material_type(response.get("material_type"))
    tags = _normalize_tags(response.get("tags"))
    summary = _normalize_summary(response.get("summary"))
    confidence = _normalize_confidence(response.get("confidence"))

    snapshot = MaterialMetadata(
        subject=subject,
        grade=grade,
        unit_title=unit_title,
        material_type=material_type,
        tags=tags,
        summary=summary,
        confidence=confidence,
        visible_text=text,
        search_text="",
    )
    search_text = _build_search_text_from_metadata(material, snapshot)
    return MaterialMetadata(
        subject=subject,
        grade=grade,
        unit_title=unit_title,
        material_type=material_type,
        tags=tags,
        summary=summary,
        confidence=confidence,
        visible_text=text,
        search_text=search_text,
    )


def _build_search_text_from_metadata(material: NextEduMaterial, metadata: MaterialMetadata) -> str:
    chunks = [
        material.title,
        material.original_filename,
        dict(NextEduMaterial.SUBJECT_CHOICES).get(metadata.subject, ""),
        metadata.grade,
        metadata.unit_title,
        dict(NextEduMaterial.MaterialType.choices).get(metadata.material_type, ""),
        " ".join(metadata.tags),
        metadata.summary,
        material.teacher_guide,
        " ".join(material.student_questions or []),
        " ".join(material.remix_tips or []),
        metadata.visible_text[:TEXT_LIMIT],
    ]
    joined = " ".join(chunk.strip() for chunk in chunks if chunk and chunk.strip())
    return re.sub(r"\s+", " ", joined).strip()


def _normalize_subject(value: str) -> str:
    normalized = str(value or "").strip().upper()
    valid = {choice for choice, _ in NextEduMaterial.SUBJECT_CHOICES}
    return normalized if normalized in valid else "OTHER"


def _normalize_material_type(value: str) -> str:
    normalized = str(value or "").strip().lower()
    valid = {choice for choice, _ in NextEduMaterial.MaterialType.choices}
    return normalized if normalized in valid else NextEduMaterial.MaterialType.OTHER


def _normalize_tags(raw_tags) -> list[str]:
    if isinstance(raw_tags, str):
        return parse_tags_input(raw_tags)
    normalized: list[str] = []
    seen = set()
    for tag in raw_tags or []:
        cleaned = re.sub(r"\s+", " ", str(tag or "")).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned[:30])
        if len(normalized) >= TAG_LIMIT:
            break
    return normalized


def _normalize_summary(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:SUMMARY_MAX_LENGTH]


def _normalize_confidence(value) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(min(max(normalized, 0.0), 1.0), 3)


def _call_json_response(*, messages, timeout_seconds=12, attempts=2):
    last_error = None
    for attempt in range(attempts):
        try:
            raw_text = _call_with_retry_and_timeout(
                lambda: _create_chat_completion(messages=messages, timeout_seconds=timeout_seconds),
                timeout_seconds=timeout_seconds,
                attempts=1,
            )
            payload = _extract_json_payload(raw_text)
            if isinstance(payload, dict):
                return payload
            raise NextEduMaterialClassificationError("DeepSeek returned invalid JSON.")
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(0.8)
    if isinstance(last_error, NextEduMaterialClassificationError):
        raise last_error
    raise NextEduMaterialClassificationError("DeepSeek request failed.") from last_error


def _create_chat_completion(*, messages, timeout_seconds):
    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise NextEduMaterialClassificationError("DeepSeek API key is not configured.")

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=float(timeout_seconds) + 6.0)
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL_NAME,
        messages=messages,
        response_format={"type": "json_object"},
        stream=False,
    )
    text = (response.choices[0].message.content or "").strip()
    if text:
        return text
    raise NextEduMaterialClassificationError("DeepSeek returned an empty response.")


def _extract_json_payload(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        raise NextEduMaterialClassificationError("DeepSeek returned an empty response.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise NextEduMaterialClassificationError("DeepSeek returned invalid JSON.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise NextEduMaterialClassificationError("DeepSeek returned invalid JSON.") from exc


def _call_with_retry_and_timeout(callable_fn, timeout_seconds, attempts=2):
    last_error = None
    for index in range(attempts):
        try:
            return _run_with_timeout(callable_fn, timeout_seconds=timeout_seconds)
        except Exception as exc:
            last_error = exc
            if index < attempts - 1:
                time.sleep(0.8)
    if isinstance(last_error, NextEduMaterialClassificationError):
        raise last_error
    raise NextEduMaterialClassificationError("LLM API call failed.") from last_error


def _run_with_timeout(callable_fn, timeout_seconds):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_fn)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise NextEduMaterialClassificationError("LLM request timed out.") from exc

