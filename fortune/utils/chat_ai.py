import os
import logging
from openai import OpenAI
from ..models import ChatMessage

logger = logging.getLogger(__name__)

DEEPSEEK_MODEL_NAME = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

def get_ai_response_stream(session, system_prompt, history, user_message):
    """
    Stream AI response from DeepSeek using OpenAI SDK.
    Accumules full response and saves it to ChatMessage at the end.
    """
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add history
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    # Configure client
    api_key = os.environ.get('MASTER_DEEPSEEK_API_KEY')
    if not api_key:
        logger.error("[Fortune] DeepSeek API Key missing (MASTER_DEEPSEEK_API_KEY)")
        yield "시스템 설정 오류: AI API 키가 없습니다.".encode('utf-8')
        return

    client = OpenAI(
        api_key=api_key, 
        base_url=DEEPSEEK_BASE_URL
    )
    
    full_response = ""
    
    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL_NAME,
            messages=messages,
            stream=True
        )
        
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content.encode('utf-8')
                
    except Exception as e:
        logger.error(f"[Fortune] Action: AI_STREAM, Status: FAIL, Error: {str(e)}")
        yield f"죄송합니다. 오류가 발생했습니다: {str(e)}".encode('utf-8')
        return

    # Save Assistant Message
    if full_response:
        ChatMessage.objects.create(session=session, role='assistant', content=full_response)
        logger.info(f"[Fortune] Action: CHAT_MSG_AI, Status: SAVED, SessionID: {session.id}")
