import hashlib
import json
import logging
import re
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone

PIPELINE_VERSION = "workitem-v1"
DEFAULT_PROVIDER = "deepseek"
MAX_HWPX_FILE_BYTES = 15 * 1024 * 1024
FULL_TEXT_CHAR_LIMIT = 40000
COMPRESSED_TEXT_CHAR_LIMIT = 20000
ABSOLUTE_TEXT_CHAR_LIMIT = 120000
MAX_WORK_ITEMS = 20
STRUCTURE_LIMITS = [(600, 5), (86400, 20)]
ASK_LIMITS = [(600, 10), (86400, 60)]
STRUCTURE_KEYWORDS = (
    "날짜",
    "마감",
    "제출",
    "준비물",
    "신청",
    "회의",
    "배부",
    "안내",
    "협조",
    "필수",
    "등록",
    "참석",
    "회신",
    "업로드",
)
LIMIT_MESSAGE = "오늘 구조화 한도를 다 사용했어요. 저장된 결과를 다시 활용해 주세요."
ASK_LIMIT_MESSAGE = "오늘 질문 한도를 다 사용했어요. 저장된 결과를 다시 활용해 주세요."
TOO_LARGE_MESSAGE = "문서가 너무 길어 나눠 올려 주세요."
logger = logging.getLogger(__name__)


def log_hwpx_metric(event_name, **fields):
    payload = {"event": str(event_name or "").strip() or "unknown"}
    payload.update(fields or {})
    logger.info("[hwpx_metric] %s", json.dumps(payload, ensure_ascii=False, default=str))


def rate_limit_exceeded(bucket_name, user_id, limits):
    now_ts = int(timezone.now().timestamp())
    for window_seconds, max_count in limits:
        slot = now_ts // window_seconds
        cache_key = f"hwpxchat:rate:{bucket_name}:{user_id}:{window_seconds}:{slot}"
        current = cache.get(cache_key)
        if current is None:
            cache.set(cache_key, 1, timeout=window_seconds + 2)
            current = 1
        else:
            try:
                current = cache.incr(cache_key)
            except Exception:
                current = int(current) + 1
                cache.set(cache_key, current, timeout=window_seconds + 2)
        if current > max_count:
            return True
    return False


def compute_sha256(raw_bytes):
    return hashlib.sha256(raw_bytes or b"").hexdigest()


def summarize_text_for_structure(raw_markdown, parse_payload):
    text = (raw_markdown or "").strip()
    blocks = list((parse_payload or {}).get("blocks") or [])
    char_count = len(text)
    if char_count <= FULL_TEXT_CHAR_LIMIT:
        return text, "full", False
    if char_count > ABSOLUTE_TEXT_CHAR_LIMIT:
        return "", "too_large", True

    keyword_hits = []
    lower_keywords = [keyword.lower() for keyword in STRUCTURE_KEYWORDS]
    for index, block in enumerate(blocks):
        block_text = str(block.get("text") or block.get("markdown") or "").strip()
        if not block_text:
            continue
        lowered = block_text.lower()
        if any(keyword in lowered for keyword in lower_keywords):
            keyword_hits.extend([index - 1, index, index + 1])

    selected_indexes = []
    seen = set()
    for index in keyword_hits:
        if index < 0 or index >= len(blocks) or index in seen:
            continue
        seen.add(index)
        selected_indexes.append(index)

    if not selected_indexes:
        selected_indexes = list(range(min(len(blocks), 12)))

    selected_texts = []
    total_chars = 0
    for index in selected_indexes:
        block = blocks[index]
        block_text = str(block.get("markdown") or block.get("text") or "").strip()
        if not block_text:
            continue
        prefix = f"[{block.get('section_label') or 'section'}]\n"
        candidate = f"{prefix}{block_text}".strip()
        separator_length = 2 if selected_texts else 0
        projected_length = total_chars + separator_length + len(candidate)
        if projected_length > COMPRESSED_TEXT_CHAR_LIMIT:
            if not selected_texts:
                selected_texts.append(candidate[:COMPRESSED_TEXT_CHAR_LIMIT].strip())
                total_chars = len(selected_texts[0])
            break
        selected_texts.append(candidate)
        total_chars = projected_length

    compressed = "\n\n".join(selected_texts).strip()
    if not compressed:
        compressed = text[:COMPRESSED_TEXT_CHAR_LIMIT].strip()
    return compressed, "compressed", False


def normalize_question(question):
    compact = re.sub(r"\s+", " ", str(question or "").strip())
    return compact[:300]


def tokenize_search_text(value):
    return [token.lower() for token in re.findall(r"[0-9A-Za-z가-힣]+", str(value or "")) if token.strip()]


def find_relevant_chunks(parse_payload, question, *, limit=5):
    chunks = list((parse_payload or {}).get("chunks") or [])
    if not chunks:
        return []

    question_tokens = tokenize_search_text(question)
    keyword_tokens = [keyword for keyword in STRUCTURE_KEYWORDS if keyword in str(question or "")]
    scored = []
    for chunk in chunks:
        text = str(chunk.get("text") or chunk.get("markdown") or "")
        lowered = text.lower()
        token_score = sum(1 for token in question_tokens if token and token in lowered)
        keyword_score = sum(2 for keyword in keyword_tokens if keyword in text)
        evidence_score = 1 if chunk.get("has_evidence") else 0
        score = token_score + keyword_score + evidence_score
        if score <= 0:
            continue
        scored.append((score, len(text), chunk))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk for _, _, chunk in scored[:limit]]


def build_fallback_work_item(raw_markdown, parse_payload, *, reason=""):
    evidence_text = str((parse_payload or {}).get("first_text_block") or "").strip()
    if not evidence_text:
        evidence_text = str(raw_markdown or "").strip()[:200]
    title = "문서 확인 필요"
    if reason == "limit_blocked":
        title = "문서 확인 필요"
    return {
        "title": title,
        "action_text": "원문을 보고 해야 할 일을 직접 정리해 주세요.",
        "due_date": None,
        "start_time": None,
        "end_time": None,
        "is_all_day": False,
        "assignee_text": "",
        "target_text": "",
        "materials_text": "",
        "delivery_required": False,
        "evidence_text": evidence_text,
        "evidence_refs_json": [],
        "confidence_score": 0,
    }


def localize_due_date_to_event_window(due_date, *, start_time=None, end_time=None, is_all_day=True):
    if due_date is None:
        return None, None, True
    if not start_time:
        start_dt = datetime.combine(due_date, datetime.min.time())
        end_dt = start_dt + timedelta(days=1)
        return timezone.make_aware(start_dt), timezone.make_aware(end_dt), True

    start_dt = datetime.combine(due_date, start_time)
    resolved_end_time = end_time or (datetime.combine(due_date, start_time) + timedelta(hours=1)).time()
    end_dt = datetime.combine(due_date, resolved_end_time)
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(hours=1)
    return timezone.make_aware(start_dt), timezone.make_aware(end_dt), bool(is_all_day and not start_time)
