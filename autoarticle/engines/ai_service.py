import os
import re
from google import genai
from google.genai import types
from openai import OpenAI

GEMINI_MODEL_NAME = "gemini-2.5-flash-lite"
# DeepSeek V3 chat endpoint is exposed via the chat-completions API.
DEEPSEEK_MODEL_NAME = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def _build_style_prompt(topic_data, style_service):
    if not style_service:
        return ""
    try:
        query = f"{topic_data.get('tone', '')} {topic_data.get('event_name', '')}".strip()
        examples = style_service.retrieve_style_examples(query)
    except Exception:
        return ""

    if not examples:
        return ""

    lines = ["\n[스타일 참고 예시]\n"]
    for i, ex in enumerate(examples[:3], start=1):
        corrected = ex.get("corrected", "")
        if corrected:
            lines.append(f"예시 {i}: {corrected}\n")
    lines.append("위 말투/문장 길이/표현 밀도를 참고해 작성하세요.\n")
    return "".join(lines)


def _parse_article_text(text, fallback_title):
    title = fallback_title or "학교 소식"
    content = text.strip()
    hashtags = re.findall(r"#([\w가-힣_]+)", text)[:5]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip() or title
            content = content.replace(line, "", 1).strip()
            break
        if line.startswith("제목:"):
            title = line.replace("제목:", "", 1).strip() or title
            content = content.replace(line, "", 1).strip()
            break

    if hashtags:
        cleaned = []
        for line in content.splitlines():
            parts = line.split()
            if parts and all(p.startswith("#") for p in parts):
                continue
            cleaned.append(line)
        content = "\n".join(cleaned).strip()

    return title, content, hashtags


def generate_article_gemini(api_key, topic_data, style_service=None, is_master_key=False):
    """
    Legacy function name kept for compatibility.
    - is_master_key=False: Gemini (user key)
    - is_master_key=True: DeepSeek (master key)
    """
    if not api_key:
        return "AI 생성 오류", "API key is missing", []

    style_prompt = _build_style_prompt(topic_data, style_service)
    prompt = f"""
당신은 초등학교 소식지를 작성하는 전문 기자입니다.

학교: {topic_data.get('school', '')}
학년: {topic_data.get('grade', '')}
행사명: {topic_data.get('event_name', '')}
장소: {topic_data.get('location', '')}
일시: {topic_data.get('date', '')}
키워드: {topic_data.get('keywords', '')}
톤: {topic_data.get('tone', '')}
{style_prompt}
요구사항:
1. 제목 1줄 (형식: 제목: ...)
2. 본문 400~600자
3. 초등학생도 이해하기 쉬운 문장
4. 문단 구분 명확하게 작성
5. 마지막에 해시태그 5개 이내 (#태그)
"""

    try:
        if is_master_key:
            client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a professional school news writer."},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
            )
            text = (resp.choices[0].message.content or "").strip()
        else:
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                safety_settings=[
                    types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
                    types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                    types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
                    types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
                ]
            )
            resp = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
                config=config,
            )
            text = (resp.text or "").strip()

        return _parse_article_text(text, topic_data.get("event_name"))
    except Exception as e:
        return "AI 생성 오류", str(e), []


def summarize_article_for_ppt(content, api_key=None, is_master_key=False):
    if not content:
        return []
    if not api_key:
        return [content[:100] + "..."]

    prompt = f"""
다음 기사 내용을 PPT용 핵심 요약으로 정리하세요.
조건:
- 3~5개 문장
- 한 줄에 한 문장
- 친근한 문체
- 불필요한 설명 없이 요약 문장만 출력

기사:
{content}
"""

    try:
        if is_master_key:
            client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You summarize school news for PPT slides."},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
            )
            text = (resp.choices[0].message.content or "").strip()
        else:
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                safety_settings=[
                    types.SafetySetting(category='HARM_CATEGORY_HARASSMENT', threshold='BLOCK_NONE'),
                    types.SafetySetting(category='HARM_CATEGORY_HATE_SPEECH', threshold='BLOCK_NONE'),
                    types.SafetySetting(category='HARM_CATEGORY_SEXUALLY_EXPLICIT', threshold='BLOCK_NONE'),
                    types.SafetySetting(category='HARM_CATEGORY_DANGEROUS_CONTENT', threshold='BLOCK_NONE'),
                ]
            )
            resp = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
                config=config,
            )
            text = (resp.text or "").strip()

        lines = [line.strip().lstrip("*- ") for line in text.splitlines() if line.strip()]
        return lines[:5] if lines else [content[:100] + "..."]
    except Exception:
        return [content[:100] + "..."]
