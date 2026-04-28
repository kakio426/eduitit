import logging
import os

from openai import OpenAI

from fortune.utils.circuit_breaker import ai_circuit_breaker

from .prompts import build_messages

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
