from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from openai import OpenAI


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"


class LlmClientError(Exception):
    pass


def _get_api_key() -> str:
    return str(os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or "").strip()


def is_configured() -> bool:
    return bool(_get_api_key())


def _truncate_prompt_quote(value: str, *, limit: int = 900) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def generate_legal_answer(*, question: str, profile: dict, citations: list[dict], timeout_seconds: int = 12) -> dict:
    if not is_configured():
        raise LlmClientError("DeepSeek API key is not configured.")

    citation_lines = []
    for citation in citations:
        source_type = "판례" if citation.get("source_type") == "case" else "법령"
        citation_lines.append(
            "\n".join(
                [
                    f"[citation_id={citation.get('citation_id')}]",
                    f"근거 유형: {source_type}",
                    f"제목: {citation.get('title') or citation.get('law_name')}",
                    f"참조: {citation.get('reference_label') or citation.get('article_label')}",
                    f"근거: {_truncate_prompt_quote(citation.get('quote'))}",
                ]
            )
        )

    prompt = (
        "당신은 교사를 위한 법령 정보 요약 도우미입니다. "
        "반드시 JSON 객체만 반환하세요. "
        "주어진 근거 외의 조문이나 판례를 지어내지 마세요. "
        "법령은 1차 근거이고 판례는 2차 보조 근거입니다. "
        "판례가 있더라도 법령보다 앞세워 단정하지 마세요. "
        "summary는 220자 이하, action_items는 1~4개, "
        "citations는 선택한 citation_id 배열, risk_level은 low/medium/high 중 하나입니다. "
        "근거가 약하면 summary에 '추가 확인 필요'를 포함하고 needs_human_help를 true로 올리세요. "
        "scope_supported는 반드시 true 또는 false로 반환하세요."
    )
    user_prompt = "\n\n".join(
        [
            f"질문: {question}",
            f"정규화 질문: {profile.get('normalized_question')}",
            f"사건 유형: {profile.get('incident_type') or profile.get('topic') or '미분류'}",
            f"궁금한 것: {profile.get('legal_goal_label') or profile.get('legal_goal') or '없음'}",
            f"행위 주체: {', '.join(profile.get('actors') or []) or '없음'}",
            f"상대: {profile.get('counterpart_label') or '없음'}",
            f"쟁점: {', '.join(profile.get('legal_issues') or []) or '없음'}",
            f"장면: {', '.join(profile.get('scene') or []) or '없음'}",
            f"위험 플래그: {', '.join(profile.get('risk_flags') or []) or '없음'}",
            "근거 목록:",
            "\n\n".join(citation_lines).strip(),
            "",
            "JSON 스키마:",
            json.dumps(
                {
                    "summary": "",
                    "action_items": [""],
                    "citations": [""],
                    "risk_level": "medium",
                    "needs_human_help": False,
                    "disclaimer": "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다.",
                    "scope_supported": True,
                },
                ensure_ascii=False,
            ),
        ]
    ).strip()

    payload = _call_json_response(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_prompt},
        ],
        timeout_seconds=timeout_seconds,
    )
    action_items = payload.get("action_items") or []
    if not isinstance(action_items, list):
        action_items = []
    citations_result = payload.get("citations") or []
    if not isinstance(citations_result, list):
        citations_result = []
    return {
        "summary": str(payload.get("summary") or "").strip(),
        "action_items": [str(item).strip() for item in action_items if str(item).strip()][:4],
        "citations": [str(item).strip() for item in citations_result if str(item).strip()],
        "risk_level": str(payload.get("risk_level") or "medium").strip().lower() or "medium",
        "needs_human_help": bool(payload.get("needs_human_help")),
        "disclaimer": str(
            payload.get("disclaimer") or "일반적 법령 정보 안내이며 개별 사건의 법률 자문은 아닙니다."
        ).strip(),
        "scope_supported": bool(payload.get("scope_supported", True)),
    }


def _call_json_response(*, messages, timeout_seconds=12, attempts=2):
    last_error = None
    for attempt in range(attempts):
        try:
            raw_text = _call_with_timeout(lambda: _create_chat_completion(messages=messages), timeout_seconds)
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
    client = OpenAI(api_key=_get_api_key(), base_url=DEEPSEEK_BASE_URL, timeout=45.0)
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


def _call_with_timeout(callable_fn, timeout_seconds):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_fn)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise LlmClientError("LLM request timed out.") from exc
