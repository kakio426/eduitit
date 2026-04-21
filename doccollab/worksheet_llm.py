import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from openai import OpenAI


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"
WORKSHEET_PROMPT_VERSION = "worksheet-v1"
ALLOWED_SYMBOLS = {"☆", "♡", "♪", "•", "ᴗ"}
ALLOWED_EMOTICONS = {"(•ᴗ•)"}


class WorksheetLlmError(Exception):
    """Raised when worksheet generation fails."""


def generate_worksheet_content(*, topic, force_short=False, timeout_seconds=45):
    normalized_topic = str(topic or "").strip()
    if not normalized_topic:
        raise WorksheetLlmError("학습 주제를 먼저 입력해 주세요.")

    system_prompt = _worksheet_system_prompt(force_short=force_short)
    user_prompt = (
        "학습 주제:\n"
        f"{normalized_topic}\n\n"
        "반드시 JSON 객체만 반환하세요."
    )
    payload = _call_json_response(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        timeout_seconds=timeout_seconds,
    )
    return normalize_worksheet_payload(payload, topic=normalized_topic)


def normalize_worksheet_payload(payload, *, topic):
    if not isinstance(payload, dict):
        raise WorksheetLlmError("DeepSeek returned invalid JSON.")

    title = _clean_text(payload.get("title"), limit=60) or f"{_clean_text(topic, limit=40)} 학습지"
    companion_line = _clean_text(payload.get("companion_line"), limit=90)
    curiosity_opening = _clean_text(payload.get("curiosity_opening"), limit=260)

    key_points_raw = payload.get("key_points") or []
    if not isinstance(key_points_raw, list):
        key_points_raw = []
    key_points = [_clean_text(item, limit=85) for item in key_points_raw if _clean_text(item, limit=85)]
    while len(key_points) < 3:
        key_points.append("")
    key_points = key_points[:3]

    quiz_items_raw = payload.get("quiz_items") or []
    if not isinstance(quiz_items_raw, list):
        quiz_items_raw = []
    quiz_items = []
    for item in quiz_items_raw:
        if isinstance(item, dict):
            prompt = _clean_text(item.get("prompt"), limit=140)
            answer_lines = _normalize_answer_lines(item.get("answer_lines"))
        else:
            prompt = _clean_text(item, limit=140)
            answer_lines = 1
        if not prompt:
            continue
        quiz_items.append(
            {
                "prompt": _ensure_prompt_has_blank(prompt),
                "answer_lines": answer_lines,
            }
        )
    while len(quiz_items) < 2:
        quiz_items.append(
            {
                "prompt": "",
                "answer_lines": 1,
            }
        )
    quiz_items = quiz_items[:2]

    visible_parts = [title, companion_line, curiosity_opening]
    visible_parts.extend(item for item in key_points if item)
    visible_parts.extend(item["prompt"] for item in quiz_items if item["prompt"])
    summary_text = _clean_text(
        payload.get("summary_text") or " ".join(part for part in [companion_line, key_points[0]] if part),
        limit=120,
    )
    search_text = "\n".join(part for part in visible_parts if part).strip()

    return {
        "title": title,
        "companion_line": companion_line,
        "curiosity_opening": curiosity_opening,
        "key_points": key_points,
        "quiz_items": quiz_items,
        "summary_text": summary_text,
        "search_text": search_text,
    }


def _worksheet_system_prompt(*, force_short):
    character_limit = "320~380자" if force_short else "400~500자"
    return (
        "당신은 초등학교 3학년 학습지를 만드는 선생님 도우미입니다. "
        "반드시 JSON 객체만 반환하세요. "
        "대상은 초등학교 3학년이며, 말투는 친절하고 다정한 선생님 또는 보라색 왈라비 안내자처럼 "
        "따뜻하게 ~해요, ~해볼까요? 형태를 사용하세요. "
        "구조는 title, companion_line, curiosity_opening, key_points, quiz_items를 포함해야 합니다. "
        "title은 18자 안팎, companion_line은 한 줄, curiosity_opening은 일상 예시나 짧은 이야기로 시작하세요. "
        "key_points는 정확히 3개 배열로, 한 항목당 짧은 문장 1개씩 넣으세요. "
        "quiz_items는 정확히 2개 배열로, 각 항목은 prompt와 answer_lines를 포함하세요. "
        "퀴즈는 객관식이 아니라 빈칸 채우기나 짧은 상상 글쓰기여야 하며, prompt 안에 답을 적을 빈칸 _____ 을 자연스럽게 넣으세요. "
        f"전체 보이는 글자 수는 반드시 {character_limit} 안쪽으로 맞추세요. "
        "허용되는 귀여운 기호는 ☆, ♡, ♪, (•ᴗ•) 뿐입니다. 다른 이모지나 특수문자는 넣지 마세요. "
        "설명은 쉬운 낱말로 쓰고, 학생이 바로 읽고 따라 쓸 수 있게 짧고 또렷하게 써 주세요."
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
            raise WorksheetLlmError("DeepSeek returned invalid JSON.")
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(1.0)
    if isinstance(last_error, WorksheetLlmError):
        raise last_error
    raise WorksheetLlmError("DeepSeek request failed.") from last_error


def _create_chat_completion(*, messages):
    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise WorksheetLlmError("DeepSeek API key is not configured.")

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
    raise WorksheetLlmError("DeepSeek returned an empty response.")


def _extract_json_payload(raw_text):
    text = str(raw_text or "").strip()
    if not text:
        raise WorksheetLlmError("DeepSeek returned an empty response.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise WorksheetLlmError("DeepSeek returned invalid JSON.")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise WorksheetLlmError("DeepSeek returned invalid JSON.") from exc


def _call_with_retry_and_timeout(callable_fn, timeout_seconds, attempts=2):
    last_error = None
    for index in range(attempts):
        try:
            return _run_with_timeout(callable_fn, timeout_seconds=timeout_seconds)
        except Exception as exc:
            last_error = exc
            if index < attempts - 1:
                time.sleep(1.0)

    if isinstance(last_error, WorksheetLlmError):
        raise last_error
    raise WorksheetLlmError("LLM API call failed.") from last_error


def _run_with_timeout(callable_fn, timeout_seconds):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_fn)
        try:
            return future.result(timeout=timeout_seconds)
        except TimeoutError as exc:
            raise WorksheetLlmError("LLM request timed out.") from exc


def _normalize_answer_lines(value):
    try:
        lines = int(value)
    except (TypeError, ValueError):
        return 1
    return 2 if lines >= 2 else 1


def _ensure_prompt_has_blank(prompt):
    text = _clean_text(prompt, limit=140)
    if not text:
        return ""
    if "_____" in text:
        return text
    return f"{text} _____"


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
    for emoticon in ALLOWED_EMOTICONS:
        text = text.replace(emoticon, "__ALLOWED_EMOTICON__")

    filtered = []
    for char in text:
        category = ord(char)
        if char == "__ALLOWED_EMOTICON__":
            continue
        if char in ALLOWED_SYMBOLS:
            filtered.append(char)
            continue
        if char in {"\n", " ", ".", ",", "!", "?", "~", "(", ")", "-", ":", ";", "'", '"', "[", "]", "/"}:
            filtered.append(char)
            continue
        if 0x20 <= category <= 0x7E:
            filtered.append(char)
            continue
        if 0x3131 <= category <= 0x318E or 0xAC00 <= category <= 0xD7A3:
            filtered.append(char)
            continue
        if 0x4E00 <= category <= 0x9FFF:
            filtered.append(char)
            continue
    restored = "".join(filtered).replace("__ALLOWED_EMOTICON__", "(•ᴗ•)")
    restored = re.sub(r"[^\S\n]{2,}", " ", restored)
    return restored.strip()
