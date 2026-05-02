import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from openai import OpenAI

from .document_spec import (
    DOCUMENT_PROMPT_VERSION,
    DOCUMENT_SCHEMA_VERSION,
    DOCUMENT_TYPE_LABELS,
    normalize_document_spec,
    normalize_feature_codes,
)


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"
MIN_PROMPT_CHARS = 20
MAX_PROMPT_CHARS = 2000

DOCUMENT_TYPE_GUIDES = {
    "notice": "학교 안내문 형식으로 대상, 일정, 준비물, 확인 사항이 드러나게 작성하세요.",
    "home_letter": "학부모에게 보내는 가정통신문 형식으로 인사, 안내, 협조 요청, 문의를 자연스럽게 구성하세요.",
    "plan": "교육 활동 계획안 형식으로 목적, 일정, 운영 내용, 준비, 유의점을 구성하세요.",
    "minutes": "회의록 형식으로 회의 개요, 논의 내용, 결정 사항, 후속 할 일을 구성하세요.",
    "report": "보고서 형식으로 배경, 주요 내용, 결과, 제언을 구성하세요.",
    "freeform": "요청에 맞는 교사용 업무 문서 형식으로 구성하세요.",
}


class DocumentGenerationLlmError(Exception):
    """Raised when AI document draft generation fails."""


def generate_document_content(*, document_type, prompt, selected_blocks=None, timeout_seconds=45):
    normalized_type = str(document_type or "").strip()
    normalized_prompt = _clean_text(prompt, limit=MAX_PROMPT_CHARS)
    if normalized_type not in DOCUMENT_TYPE_LABELS:
        raise DocumentGenerationLlmError("지원하지 않는 문서 종류입니다.")
    if len(normalized_prompt) < MIN_PROMPT_CHARS:
        raise DocumentGenerationLlmError("요청 내용을 20자 이상 적어 주세요.")

    normalized_blocks = normalize_feature_codes(selected_blocks)
    system_prompt = _document_system_prompt(normalized_type, selected_blocks=normalized_blocks)
    user_prompt = (
        "문서 요청:\n"
        f"{normalized_prompt}\n\n"
        f"선택 구성: {', '.join(normalized_blocks) if normalized_blocks else '문서 종류 기본값'}\n\n"
        "반드시 JSON 객체만 반환하세요."
    )
    payload = _call_json_response(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        timeout_seconds=timeout_seconds,
    )
    return normalize_document_payload(
        payload,
        document_type=normalized_type,
        prompt=normalized_prompt,
        selected_blocks=normalized_blocks,
    )


def normalize_document_payload(payload, *, document_type, prompt, selected_blocks=None):
    if not isinstance(payload, dict):
        raise DocumentGenerationLlmError("DeepSeek returned invalid JSON.")
    return normalize_document_spec(
        payload,
        document_type=document_type,
        prompt=prompt,
        selected_blocks=selected_blocks,
    )


def _normalize_body_blocks(value):
    if not isinstance(value, list):
        return []
    blocks = []
    for item in value:
        if isinstance(item, dict):
            heading = _clean_text(item.get("heading"), limit=80)
            paragraphs = _normalize_string_list(item.get("paragraphs") or item.get("body"), limit=420, max_items=3)
            bullets = _normalize_string_list(item.get("bullets"), limit=160, max_items=5)
        else:
            heading = ""
            paragraphs = [_clean_text(item, limit=420)]
            bullets = []
        paragraphs = [line for line in paragraphs if line]
        bullets = [line for line in bullets if line]
        if heading or paragraphs or bullets:
            blocks.append(
                {
                    "heading": heading,
                    "paragraphs": paragraphs,
                    "bullets": bullets,
                }
            )
        if len(blocks) >= 8:
            break
    return blocks


def _normalize_string_list(value, *, limit, max_items):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = _clean_text(item, limit=limit)
        if text:
            result.append(text)
        if len(result) >= max_items:
            break
    return result


def _document_system_prompt(document_type, *, selected_blocks=None):
    label = DOCUMENT_TYPE_LABELS[document_type]
    guide = DOCUMENT_TYPE_GUIDES[document_type]
    selected_text = ", ".join(selected_blocks or []) or "문서 종류 기본값"
    return (
        "당신은 학교 교사의 업무 문서 초안을 작성하는 문서 비서입니다. "
        "반드시 JSON 객체만 반환하세요. "
        f"문서 종류는 {label}입니다. {guide} "
        f"schema_version은 반드시 {DOCUMENT_SCHEMA_VERSION}입니다. "
        "title, subtitle, summary_text, blocks 키를 포함하세요. "
        "blocks는 type을 가진 객체 배열이며 허용 type은 "
        "masthead, title, meta_table, paragraph, bullet_list, info_table, schedule_table, "
        "decision_table, budget_table, callout_box, signature_box 뿐입니다. "
        "표 블록은 title, headers, rows를 가지며 headers는 최대 5개, rows는 최대 8개입니다. "
        "paragraph는 title과 text, bullet_list는 title과 items를 사용하세요. "
        "masthead에는 school_name, department, contact, fax를 넣고 모르면 ○○학교와 빈 값을 사용하세요. "
        f"교사가 선택한 구성은 {selected_text}입니다. 선택 구성은 가능한 한 해당 블록으로 반영하세요. "
        "없는 정보는 지어내지 말고 빈 문자열이나 일반 표현으로 두세요. "
        "교사가 바로 수정할 수 있도록 자연스러운 한국어 공문/학교 문서 문체로 쓰세요. "
        "title은 80자 이하, 표 셀은 짧은 구절로 작성하세요. "
        "문단은 짧고 명확하게 쓰고, 과도한 장식 기호나 이모지는 넣지 마세요."
    )


def _call_json_response(*, messages, timeout_seconds=45, attempts=2):
    last_error = None
    for attempt in range(attempts):
        try:
            raw_text = _call_with_retry_and_timeout(
                lambda: _create_chat_completion(messages=messages),
                timeout_seconds=timeout_seconds,
                attempts=1,
            )
            payload = _extract_json_payload(raw_text)
            if isinstance(payload, dict):
                return payload
            raise DocumentGenerationLlmError("DeepSeek returned invalid JSON.")
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(1.0)
    if isinstance(last_error, DocumentGenerationLlmError):
        raise last_error
    raise DocumentGenerationLlmError("DeepSeek request failed.") from last_error


def _create_chat_completion(*, messages):
    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise DocumentGenerationLlmError("DeepSeek API key is not configured.")

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=45.0)
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL_NAME,
        messages=messages,
        response_format={"type": "json_object"},
        stream=False,
    )
    text = (response.choices[0].message.content or "").strip()
    if text:
        return text
    raise DocumentGenerationLlmError("DeepSeek returned an empty response.")


def _extract_json_payload(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        raise DocumentGenerationLlmError("DeepSeek returned an empty response.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise DocumentGenerationLlmError("DeepSeek returned invalid JSON.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise DocumentGenerationLlmError("DeepSeek returned invalid JSON.") from exc


def _call_with_retry_and_timeout(callable_fn, timeout_seconds, attempts=2):
    last_error = None
    for index in range(attempts):
        try:
            return _run_with_timeout(callable_fn, timeout_seconds=timeout_seconds)
        except Exception as exc:
            last_error = exc
            if index < attempts - 1:
                time.sleep(1.0)

    if isinstance(last_error, DocumentGenerationLlmError):
        raise last_error
    raise DocumentGenerationLlmError("LLM API call failed.") from last_error


def _run_with_timeout(callable_fn, timeout_seconds):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_fn)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise DocumentGenerationLlmError("LLM request timed out.") from exc


def _clean_text(value, *, limit):
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = _filter_symbols(text)
    return text[:limit].strip()


def _filter_symbols(text):
    filtered = []
    for char in text:
        code = ord(char)
        if char in {"\n", " ", ".", ",", "!", "?", "~", "(", ")", "-", ":", ";", "'", '"', "[", "]", "/", "%", "·"}:
            filtered.append(char)
            continue
        if 0x20 <= code <= 0x7E:
            filtered.append(char)
            continue
        if 0x3131 <= code <= 0x318E or 0xAC00 <= code <= 0xD7A3:
            filtered.append(char)
            continue
        if 0x4E00 <= code <= 0x9FFF:
            filtered.append(char)
            continue
    return re.sub(r"[^\S\n]{2,}", " ", "".join(filtered)).strip()
