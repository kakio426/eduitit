import logging
import json
import os
import re

from openai import OpenAI

from fortune.utils.circuit_breaker import ai_circuit_breaker

from .prompts import build_messages
from .quality import FableQualityResult

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"


class BambooLlmError(RuntimeError):
    pass


def generate_bamboo_fable(masked_text: str, *, retry_instruction: str = "") -> str:
    if not ai_circuit_breaker.can_execute():
        raise BambooLlmError("AI_TEMPORARILY_UNAVAILABLE")

    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise BambooLlmError("API_NOT_CONFIGURED")

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=45.0)
    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL_NAME,
            messages=build_messages(masked_text, retry_instruction=retry_instruction),
            temperature=0.9,
            top_p=0.95,
            max_tokens=600,
            stream=False,
        )
    except Exception as exc:
        ai_circuit_breaker.record_failure()
        logger.exception("[Bamboo] DeepSeek request failed")
        raise BambooLlmError("LLM_REQUEST_FAILED") from exc

    content = (response.choices[0].message.content or "").strip()
    if not content:
        ai_circuit_breaker.record_failure()
        raise BambooLlmError("EMPTY_OUTPUT")

    ai_circuit_breaker.record_success()
    return content


def review_bamboo_fable_quality(masked_text: str, fable_output: str) -> FableQualityResult:
    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key or not ai_circuit_breaker.can_execute():
        return FableQualityResult(is_valid=True)

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=30.0)
    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 교사 대나무숲 우화의 품질 검수자입니다. "
                        "개인정보 추론을 하지 말고, JSON만 출력하세요."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "[검수 기준]\n"
                        "- 한국어 우화가 자연스럽고 앞뒤 인과가 이어지는가\n"
                        "- 제목, 사건, 풍자 결말이 같은 이야기 안에 있는가\n"
                        "- 캐릭터가 중간에 이유 없이 바뀌거나 모순되는 행동을 하지 않는가\n"
                        "- 뜬금없는 결말, 사과문, 해명문, 프롬프트 언급이 없는가\n"
                        "- 4~8문장 본문과 숲의 속삭임 구조가 유지되는가\n\n"
                        '[출력]\n{"pass": true, "issues": []}\n'
                        '또는\n{"pass": false, "issues": ["짧은 한국어 이유"]}\n\n'
                        f"[마스킹된 입력]\n{masked_text}\n\n[우화]\n{fable_output}"
                    ),
                },
            ],
            temperature=0.1,
            top_p=0.8,
            max_tokens=220,
            stream=False,
        )
    except Exception:
        logger.exception("[Bamboo] DeepSeek quality review failed")
        return FableQualityResult(is_valid=True)

    payload = _parse_quality_payload(response.choices[0].message.content or "")
    if payload is None:
        return FableQualityResult(is_valid=True)
    issues = payload.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    cleaned = tuple(str(issue).strip()[:80] for issue in issues if str(issue).strip())
    return FableQualityResult(is_valid=bool(payload.get("pass")) and not cleaned, reasons=cleaned)


def _parse_quality_payload(content: str) -> dict | None:
    text = (content or "").strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if match:
        text = match.group(0)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
