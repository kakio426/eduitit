import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"


class MessageCaptureLlmError(Exception):
    """Raised when message capture refinement fails."""


def refine_message_capture_candidates(*, normalized_text, lines, candidates, timeout_seconds=25):
    if not candidates:
        return []

    prompt = (
        "당신은 학교 메시지에서 교사가 달력에 바로 저장할 일정 후보를 다듬는 도우미입니다. "
        "반드시 JSON 객체만 반환하세요. candidates 배열만 반환해야 하며, 각 항목에는 title, summary, kind, is_recommended, evidence_text를 포함하세요. "
        "kind는 event, deadline, prep 중 하나만 사용하세요. "
        "제목은 교사가 바로 이해할 수 있게 짧고 실용적으로 쓰고, summary는 1~2문장으로만 정리하세요. "
        "선생님 안녕하세요 같은 인사말은 제목에 넣지 마세요. "
        "규칙이 이미 강한 마감 신호(까지, 마감, 제출, 수정, 작성, 회신, 부탁)를 잡은 후보는 event로 바꾸지 마세요."
    )
    payload = {
        "message": str(normalized_text or "").strip(),
        "lines": list(lines or []),
        "candidates": [
            {
                "kind": str(candidate.get("kind") or "event"),
                "title": str(candidate.get("title") or "").strip(),
                "summary": str(candidate.get("summary") or "").strip(),
                "evidence_text": str(candidate.get("evidence_text") or "").strip(),
                "needs_check": bool(candidate.get("needs_check")),
                "is_recommended": bool(candidate.get("is_recommended", True)),
            }
            for candidate in candidates
        ],
    }
    response = _call_json_response(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        timeout_seconds=timeout_seconds,
    )
    refined = response.get("candidates") or []
    if not isinstance(refined, list):
        return []
    return refined[: len(candidates)]


def _call_json_response(*, messages, timeout_seconds=25, attempts=2):
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
            raise MessageCaptureLlmError("DeepSeek returned invalid JSON.")
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(0.8)
    if isinstance(last_error, MessageCaptureLlmError):
        raise last_error
    raise MessageCaptureLlmError("DeepSeek request failed.") from last_error


def _create_chat_completion(*, messages):
    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise MessageCaptureLlmError("DeepSeek API key is not configured.")

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=30.0)
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL_NAME,
        messages=messages,
        response_format={"type": "json_object"},
        stream=False,
    )
    text = (response.choices[0].message.content or "").strip()
    if text:
        return text
    raise MessageCaptureLlmError("DeepSeek returned an empty response.")


def _extract_json_payload(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        raise MessageCaptureLlmError("DeepSeek returned an empty response.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise MessageCaptureLlmError("DeepSeek returned invalid JSON.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise MessageCaptureLlmError("DeepSeek returned invalid JSON.") from exc


def _call_with_retry_and_timeout(callable_fn, timeout_seconds, attempts=2):
    last_error = None
    for index in range(attempts):
        try:
            return _run_with_timeout(callable_fn, timeout_seconds=timeout_seconds)
        except Exception as exc:
            last_error = exc
            if index < attempts - 1:
                time.sleep(0.8)
    if isinstance(last_error, MessageCaptureLlmError):
        raise last_error
    raise MessageCaptureLlmError("LLM API call failed.") from last_error


def _run_with_timeout(callable_fn, timeout_seconds):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_fn)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise MessageCaptureLlmError("LLM request timed out.") from exc
