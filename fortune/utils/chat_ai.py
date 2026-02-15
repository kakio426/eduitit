import os
import logging
import html
from openai import AsyncOpenAI
from ..models import ChatMessage
from asgiref.sync import sync_to_async
from .circuit_breaker import ai_circuit_breaker

logger = logging.getLogger(__name__)

DEEPSEEK_MODEL_NAME = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MARKDOWN_CHARS = "*_`#>[]<"


def _strip_markdown_chars(text):
    if not text:
        return ""
    return "".join(ch for ch in text if ch not in MARKDOWN_CHARS)


def _sanitize_stream_chunk(text):
    # Streamed chunks are injected directly into HTML; escape to prevent XSS.
    plain = _strip_markdown_chars(text)
    return html.escape(plain, quote=False).replace("\n", "<br>")

async def get_ai_response_stream(session, system_prompt, history, user_message):
    """
    Stream AI response from DeepSeek using AsyncOpenAI SDK.
    Accumulates full response and saves it to ChatMessage at the end.
    """
    messages = [{"role": "system", "content": system_prompt}]

    # Add history (QuerySet -> list, needs sync_to_async)
    history_list = await sync_to_async(list)(history.values('role', 'content'))
    for msg in history_list:
        messages.append({"role": msg['role'], "content": msg['content']})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    # Circuit breaker check
    if not ai_circuit_breaker.can_execute():
        yield "AI 서비스가 일시적으로 불안정합니다. 잠시 후 다시 시도해주세요."
        return

    # Configure client
    api_key = os.environ.get('MASTER_DEEPSEEK_API_KEY')
    if not api_key:
        logger.error("[Fortune] DeepSeek API Key missing (MASTER_DEEPSEEK_API_KEY)")
        yield "시스템 설정 오류: AI API 키가 없습니다."
        return

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
        timeout=60.0,
    )

    full_response = ""

    try:
        response = await client.chat.completions.create(
            model=DEEPSEEK_MODEL_NAME,
            messages=messages,
            stream=True
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                plain_content = _strip_markdown_chars(chunk.choices[0].delta.content)
                full_response += plain_content
                yield _sanitize_stream_chunk(chunk.choices[0].delta.content)

    except Exception as e:
        ai_circuit_breaker.record_failure()
        logger.error(f"[Fortune] Action: AI_STREAM, Status: FAIL, Error: {str(e)}")
        yield f"죄송합니다. 오류가 발생했습니다: {str(e)}"
        return

    # Save Assistant Message
    ai_circuit_breaker.record_success()
    if full_response:
        await ChatMessage.objects.acreate(session=session, role='assistant', content=full_response)
        logger.info(f"[Fortune] Action: CHAT_MSG_AI, Status: SAVED, SessionID: {session.id}")
