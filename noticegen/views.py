import hashlib
import logging
import os
import re
from difflib import SequenceMatcher

from django.db.models import F
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST
from openai import OpenAI

from products.models import Product

from .models import (
    NoticeGenerationAttempt,
    NoticeGenerationCache,
    TARGET_CHOICES,
    TOPIC_CHOICES,
)
from .prompts import (
    PROMPT_VERSION,
    TARGET_LABELS,
    TOPIC_LABELS,
    build_system_prompt,
    build_user_prompt,
    get_tone_for_target,
)

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_NAME = "deepseek-chat"

SERVICE_TITLE = "알림장 & 주간학습 멘트 생성기"
CONTEXT_CHOICES = [
    ("rain_snow_dust", "비/눈/미세먼지"),
    ("weekend_holiday", "주말/연휴 인사"),
    ("health_cold", "건강/감기 조심"),
]
CONTEXT_LABELS = dict(CONTEXT_CHOICES)

CACHE_REUSE_THRESHOLD = 0.88
CACHE_SIMILAR_HINT_THRESHOLD = 0.55
SIMILAR_CANDIDATE_LIMIT = 60
FALLBACK_ERROR_MESSAGE = "멘트 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


def _result_defaults():
    return {
        "result_text": "",
        "error_message": "",
        "info_message": "",
        "limit_message": "",
        "remaining_count": None,
        "daily_limit": None,
        "similar_items": [],
    }


def _get_service():
    service = Product.objects.filter(launch_route_name="noticegen:main").first()
    if service:
        return service
    return Product.objects.filter(title=SERVICE_TITLE).first()


def _build_page_context():
    return {
        "service": _get_service(),
        "target_options": TARGET_CHOICES,
        "topic_options": TOPIC_CHOICES,
        "context_options": CONTEXT_CHOICES,
    }


def _ensure_session_key(request):
    if request.user.is_authenticated:
        return ""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ""


def _daily_limit(request):
    return 10 if request.user.is_authenticated else 5


def _usage_count_today(request):
    today = timezone.localdate()
    qs = NoticeGenerationAttempt.objects.filter(charged=True, created_at__date=today)
    if request.user.is_authenticated:
        return qs.filter(user=request.user).count()
    session_key = _ensure_session_key(request)
    return qs.filter(user__isnull=True, session_key=session_key).count()


def _remaining_count(request):
    limit = _daily_limit(request)
    used = _usage_count_today(request)
    return max(limit - used, 0)


def _record_attempt(
    request,
    *,
    target,
    topic,
    tone,
    status,
    charged=False,
    key_hash="",
    error_code="",
):
    session_key = "" if request.user.is_authenticated else _ensure_session_key(request)
    user = request.user if request.user.is_authenticated else None
    return NoticeGenerationAttempt.objects.create(
        user=user,
        session_key=session_key,
        target=target,
        topic=topic,
        tone=tone,
        key_hash=key_hash,
        charged=charged,
        status=status,
        error_code=error_code,
    )


def _normalize_text(value):
    value = (value or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value


def _normalize_context_values(raw_values):
    allowed = set(CONTEXT_LABELS.keys())
    cleaned = sorted({value for value in raw_values if value in allowed})
    return cleaned


def _build_cache_key_data(target, topic, tone, keywords, context_values):
    keywords_norm = _normalize_text(keywords)
    context_norm = "|".join(context_values)
    signature = f"{PROMPT_VERSION}|{target}|{topic}|{tone}|{keywords_norm}|{context_norm}"
    key_hash = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return {
        "keywords_norm": keywords_norm,
        "context_norm": context_norm,
        "signature": signature,
        "key_hash": key_hash,
    }


def _serialize_context_values(context_values):
    labels = [CONTEXT_LABELS[value] for value in context_values if value in CONTEXT_LABELS]
    return ", ".join(labels)


def _touch_cache(cache_obj):
    NoticeGenerationCache.objects.filter(pk=cache_obj.pk).update(
        hit_count=F("hit_count") + 1,
        last_used_at=timezone.now(),
    )


def _find_exact_cache(key_hash):
    return NoticeGenerationCache.objects.filter(key_hash=key_hash).first()


def _collect_similar_caches(target, topic, tone, signature):
    candidates = NoticeGenerationCache.objects.filter(
        target=target,
        topic=topic,
        tone=tone,
        prompt_version=PROMPT_VERSION,
    ).order_by("-last_used_at")[:SIMILAR_CANDIDATE_LIMIT]

    scored = []
    for item in candidates:
        score = SequenceMatcher(None, signature, item.signature).ratio()
        if score >= CACHE_SIMILAR_HINT_THRESHOLD:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def _classify_error_code(exc):
    text = str(exc).lower()
    if "timeout" in text:
        return "TIMEOUT"
    if "api_not_configured" in text:
        return "API_NOT_CONFIGURED"
    if "429" in text:
        return "UPSTREAM_RATE_LIMIT"
    return "LLM_ERROR"


def _call_deepseek(system_prompt, user_prompt):
    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("API_NOT_CONFIGURED")

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=45.0)
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=False,
    )
    return (response.choices[0].message.content or "").strip()


def _sanitize_output_text(raw_text):
    if not raw_text:
        return ""

    lines = []
    for raw_line in raw_text.splitlines():
        cleaned = re.sub(r"^\s*[-*•\d\)\.]+\s*", "", raw_line).strip()
        if cleaned:
            lines.append(cleaned)

    if not lines:
        return ""

    compact = " ".join(lines)
    sentence_candidates = [s.strip() for s in re.split(r"(?<=[.!?])\s+", compact) if s.strip()]
    if not sentence_candidates:
        sentence_candidates = lines

    selected = sentence_candidates[:3]
    return "\n".join(selected).strip()


def _render_result(request, payload, *, status=200):
    context = _result_defaults()
    context.update(payload)

    if request.headers.get("HX-Request") == "true":
        return render(request, "noticegen/partials/result_panel.html", context, status=status)

    page_context = _build_page_context()
    page_context.update(context)
    return render(request, "noticegen/main.html", page_context, status=status)


def main(request):
    context = _build_page_context()
    context.update(_result_defaults())
    return render(request, "noticegen/main.html", context)


@require_POST
def generate_notice(request):
    target = (request.POST.get("target") or "").strip()
    topic = (request.POST.get("topic") or "").strip()
    keywords = (request.POST.get("keywords") or "").strip()
    context_values = _normalize_context_values(request.POST.getlist("contexts"))

    if target not in TARGET_LABELS or topic not in TOPIC_LABELS or len(keywords) < 2:
        tone = get_tone_for_target(target)
        _record_attempt(
            request,
            target=target if target in TARGET_LABELS else "student_high",
            topic=topic if topic in TOPIC_LABELS else "notice",
            tone=tone,
            status=NoticeGenerationAttempt.STATUS_VALIDATION_FAIL,
            charged=False,
            error_code="INVALID_INPUT",
        )
        return _render_result(
            request,
            {
                "error_message": "대상, 주제, 전달 사항을 정확히 입력해 주세요.",
            },
            status=400,
        )

    tone = get_tone_for_target(target)
    key_data = _build_cache_key_data(target, topic, tone, keywords, context_values)
    key_hash = key_data["key_hash"]

    exact_cache = _find_exact_cache(key_hash)
    if exact_cache:
        _touch_cache(exact_cache)
        _record_attempt(
            request,
            target=target,
            topic=topic,
            tone=tone,
            status=NoticeGenerationAttempt.STATUS_CACHE_HIT,
            charged=False,
            key_hash=key_hash,
        )
        return _render_result(
            request,
            {
                "info_message": "저장된 멘트를 불러왔습니다.",
                "result_text": exact_cache.result_text,
                "remaining_count": _remaining_count(request),
                "daily_limit": _daily_limit(request),
            },
        )

    if _usage_count_today(request) >= _daily_limit(request):
        _record_attempt(
            request,
            target=target,
            topic=topic,
            tone=tone,
            status=NoticeGenerationAttempt.STATUS_LIMIT_BLOCKED,
            charged=False,
            key_hash=key_hash,
            error_code="DAILY_LIMIT_REACHED",
        )
        return _render_result(
            request,
            {
                "limit_message": f"오늘 멘트 생성 횟수({_daily_limit(request)}회)를 모두 사용했습니다.",
                "remaining_count": 0,
                "daily_limit": _daily_limit(request),
            },
            status=429,
        )

    similar_scored = _collect_similar_caches(target, topic, tone, key_data["signature"])
    best_reuse = similar_scored[0] if similar_scored else None
    similar_items = [
        {
            "result_text": item.result_text,
            "score": int(score * 100),
        }
        for score, item in similar_scored[:3]
    ]

    if best_reuse and best_reuse[0] >= CACHE_REUSE_THRESHOLD:
        reused_cache = best_reuse[1]
        _touch_cache(reused_cache)
        _record_attempt(
            request,
            target=target,
            topic=topic,
            tone=tone,
            status=NoticeGenerationAttempt.STATUS_CACHE_HIT,
            charged=False,
            key_hash=key_hash,
        )
        return _render_result(
            request,
            {
                "info_message": "유사한 행사 멘트를 재사용했습니다. 필요하면 전달사항을 조금 바꿔 다시 생성해 보세요.",
                "result_text": reused_cache.result_text,
                "remaining_count": _remaining_count(request),
                "daily_limit": _daily_limit(request),
                "similar_items": similar_items,
            },
        )

    attempt = _record_attempt(
        request,
        target=target,
        topic=topic,
        tone=tone,
        status=NoticeGenerationAttempt.STATUS_LLM_REQUESTED,
        charged=True,
        key_hash=key_hash,
    )

    context_text = _serialize_context_values(context_values)
    system_prompt = build_system_prompt(target)
    user_prompt = build_user_prompt(target, topic, keywords, context_text)

    try:
        raw_output = _call_deepseek(system_prompt, user_prompt)
        result_text = _sanitize_output_text(raw_output)
        if not result_text:
            raise RuntimeError("EMPTY_OUTPUT")
    except Exception as exc:
        error_code = _classify_error_code(exc)
        logger.exception(
            "[NoticeGen] Action: GENERATE, Status: FAIL, ErrorCode: %s, Target: %s, Topic: %s",
            error_code,
            target,
            topic,
        )
        NoticeGenerationAttempt.objects.filter(pk=attempt.pk).update(
            status=NoticeGenerationAttempt.STATUS_LLM_FAIL,
            error_code=error_code,
        )
        return _render_result(
            request,
            {
                "error_message": FALLBACK_ERROR_MESSAGE,
                "remaining_count": _remaining_count(request),
                "daily_limit": _daily_limit(request),
                "similar_items": similar_items,
            },
        )

    NoticeGenerationAttempt.objects.filter(pk=attempt.pk).update(
        status=NoticeGenerationAttempt.STATUS_LLM_SUCCESS,
        error_code="",
    )

    NoticeGenerationCache.objects.update_or_create(
        key_hash=key_hash,
        defaults={
            "prompt_version": PROMPT_VERSION,
            "target": target,
            "topic": topic,
            "tone": tone,
            "keywords_norm": key_data["keywords_norm"],
            "context_norm": key_data["context_norm"],
            "signature": key_data["signature"],
            "result_text": result_text,
        },
    )

    logger.info(
        "[NoticeGen] Action: GENERATE, Status: SUCCESS, Target: %s, Topic: %s",
        target,
        topic,
    )
    return _render_result(
        request,
        {
            "info_message": "멘트를 생성했습니다.",
            "result_text": result_text,
            "remaining_count": _remaining_count(request),
            "daily_limit": _daily_limit(request),
            "similar_items": similar_items,
        },
    )

