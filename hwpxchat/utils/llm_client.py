import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"


class LlmClientError(Exception):
    """Raised when LLM request fails."""


def generate_structured_workitems(*, source_text, timeout_seconds=45, max_items=20):
    prompt = (
        "당신은 학교 공문을 실행 가능한 업무 카드로 바꾸는 도우미입니다. "
        "반드시 JSON 객체만 반환하세요. summary_text는 120자 이하 한 줄이어야 합니다. "
        "work_items는 최대 {max_items}개이며, 각 항목에는 title, action_text, due_date, start_time, end_time, "
        "is_all_day, assignee_text, target_text, materials_text, delivery_required, evidence_text, confidence_score를 포함해야 합니다. "
        "날짜나 시간이 없으면 null 또는 빈 값으로 두고, evidence_text는 반드시 문서 근거 문장을 넣으세요."
    ).format(max_items=max_items)
    payload = _call_json_response(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": source_text},
        ],
        timeout_seconds=timeout_seconds,
    )
    work_items = payload.get("work_items") or []
    if not isinstance(work_items, list):
        work_items = []
    return {
        "summary_text": str(payload.get("summary_text") or "").strip()[:120],
        "work_items": work_items[:max_items],
    }


def answer_document_question(*, question, chunks, timeout_seconds=45):
    evidence_lines = []
    for chunk in chunks:
        evidence_lines.append(
            "\n".join(
                [
                    f"[chunk_id={chunk.get('id')}]",
                    str(chunk.get("markdown") or chunk.get("text") or "").strip(),
                ]
            )
        )
    user_prompt = "\n\n".join(
        [
            "질문:",
            str(question or "").strip(),
            "",
            "문서 근거:",
            "\n\n".join(evidence_lines).strip(),
        ]
    ).strip()
    prompt = (
        "당신은 문서 근거에만 기반해 답해야 합니다. 반드시 JSON 객체만 반환하세요. "
        "answer는 간결하게 작성하고, 문서 근거가 부족하면 has_insufficient_evidence를 true로 설정하세요. "
        "citations는 chunk_id와 quote를 담은 배열이어야 합니다. quote는 120자 이하로 유지하세요."
    )
    payload = _call_json_response(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_prompt},
        ],
        timeout_seconds=timeout_seconds,
    )
    citations = payload.get("citations") or []
    if not isinstance(citations, list):
        citations = []
    normalized_citations = []
    for citation in citations[:5]:
        if not isinstance(citation, dict):
            continue
        normalized_citations.append(
            {
                "chunk_id": str(citation.get("chunk_id") or "").strip(),
                "quote": str(citation.get("quote") or "").strip()[:120],
            }
        )
    return {
        "answer": str(payload.get("answer") or "").strip(),
        "citations": normalized_citations,
        "has_insufficient_evidence": bool(payload.get("has_insufficient_evidence")),
    }


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
            raise LlmClientError("DeepSeek returned invalid JSON.")
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(1.0)
    if isinstance(last_error, LlmClientError):
        raise last_error
    raise LlmClientError("DeepSeek request failed.") from last_error


def _create_chat_completion(*, messages):
    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise LlmClientError("DeepSeek API key is not configured.")

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
    raise LlmClientError("DeepSeek returned an empty response.")


def _extract_json_payload(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        raise LlmClientError("DeepSeek returned an empty response.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise LlmClientError("DeepSeek returned invalid JSON.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LlmClientError("DeepSeek returned invalid JSON.") from exc


def _call_with_retry_and_timeout(callable_fn, timeout_seconds, attempts=2):
    last_error = None
    for idx in range(attempts):
        try:
            return _run_with_timeout(callable_fn, timeout_seconds=timeout_seconds)
        except Exception as exc:
            last_error = exc
            if idx < attempts - 1:
                time.sleep(1.0)

    if isinstance(last_error, LlmClientError):
        raise last_error
    raise LlmClientError("LLM API call failed.") from last_error


def _run_with_timeout(callable_fn, timeout_seconds):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_fn)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise LlmClientError("LLM request timed out.") from exc
