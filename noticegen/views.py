import hashlib
import logging
import os
import re
import secrets
from difflib import SequenceMatcher
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django_ratelimit.core import is_ratelimited
from django.db.models import F
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from openai import OpenAI

from core.seo import build_noticegen_page_seo
from products.models import Product

from .models import (
    NoticeGenerationAttempt,
    NoticeGenerationCache,
    TARGET_CHOICES,
    TARGET_HIGH,
    TARGET_LOW,
    TARGET_PARENT,
    TOPIC_ACTIVITY,
    TOPIC_CHOICES,
    TOPIC_EVENT,
    TOPIC_NOTICE,
    TOPIC_SAFETY,
)
from .prompts import (
    LENGTH_CHOICES,
    LENGTH_LABELS,
    LENGTH_LONG,
    LENGTH_MEDIUM,
    LENGTH_RULES,
    LENGTH_SHORT,
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
DEFAULT_TARGET = TARGET_PARENT
DEFAULT_TOPIC = TOPIC_NOTICE
DEFAULT_LENGTH_STYLE = LENGTH_MEDIUM
CONTEXT_CHOICES = [
    ("rain_snow_dust", "비/눈/미세먼지"),
    ("weekend_holiday", "주말/연휴"),
    ("health_cold", "건강/감기 조심"),
    ("supplies", "준비물"),
    ("schedule_change", "일정 변경"),
    ("event_notice", "행사 안내"),
    ("cooperation_request", "협조 요청"),
]
CONTEXT_LABELS = dict(CONTEXT_CHOICES)
FRAGMENT_SPLIT_RE = re.compile(r"[\n,;]+")
BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•▪▶]+|\d+[\)\.])\s*")
EXPLICIT_DATE_PATTERN = re.compile(
    r"\d{1,2}\s*월\s*\d{1,2}\s*일|\d{1,2}\s*/\s*\d{1,2}|오늘|내일|모레|이번\s*주|다음\s*주"
)
EXPLICIT_TIME_PATTERN = re.compile(r"(?:오전|오후)?\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?|\d{1,2}:\d{2}")
LOCATION_PATTERN = re.compile(r"(?:[A-Za-z0-9가-힣]{1,12}(?:실|관)|교실|강당|운동장|현관|도서실|과학실|체육관)")
LOW_GRADE_HINT_RE = re.compile(r"저학년|1학년|2학년|우리\s*친구들|친구들아|어린이")
HIGH_GRADE_HINT_RE = re.compile(r"고학년|3학년|4학년|5학년|6학년|학생\s*여러분|반\s*친구들")
SHORT_LENGTH_HINT_RE = re.compile(r"짧게|한두\s*줄|두세\s*줄|간단히")
LONG_LENGTH_HINT_RE = re.compile(r"길게|자세히|조금\s*길게|상세히")
TOPIC_HINT_PATTERNS = (
    (TOPIC_EVENT, re.compile(r"체험학습|운동회|학예회|견학|발표회|축제|행사|현장체험")),
    (TOPIC_SAFETY, re.compile(r"안전|주의|미세먼지|황사|감기|독감|위생|퀵보드|폭염|한파")),
    (TOPIC_ACTIVITY, re.compile(r"활동|수업|준비물|만들기|과제|숙제|관찰|실험")),
)
CONTEXT_HINT_PATTERNS = {
    "rain_snow_dust": re.compile(r"비|눈|미세먼지|황사|폭우|폭설|우천"),
    "weekend_holiday": re.compile(r"주말|연휴|휴일|공휴일|쉬는\s*날"),
    "health_cold": re.compile(r"감기|건강|독감|컨디션|마스크|손\s*씻|위생|코로나"),
    "supplies": re.compile(r"준비물|지참|챙겨|가져오|도시락|물통|실내화|필기도구|우산|겉옷|마스크"),
    "schedule_change": re.compile(r"등교|하교|변경|일정|출발|도착|까지\s*오|모여|시간"),
    "event_notice": re.compile(r"체험학습|운동회|학예회|견학|발표회|축제|행사|현장체험"),
    "cooperation_request": re.compile(r"부탁|협조|회신|제출|서명|동의|확인|보내\s*주"),
}
IMPORTANT_TERM_KEYWORDS = (
    "체험학습",
    "운동회",
    "학예회",
    "행사",
    "준비물",
    "도시락",
    "물통",
    "실내화",
    "우산",
    "마스크",
    "필기도구",
    "회신",
    "제출",
    "서명",
    "동의",
    "확인",
    "등교",
    "하교",
    "복장",
)
SUSPICIOUS_OUTPUT_SNIPPETS = (
    "요구사항",
    "출력은",
    "문체",
    "대상:",
    "주제:",
    "분량:",
)
PARENT_META_INSTRUCTION_RE = re.compile(
    r"(?:도록|게)\s*(?:안내|지도|전달|말씀)해\s*주(?:세요|시기\s*바랍니다)|"
    r"(?:학생|자녀).{0,12}(?:에게|한테)\s*(?:안내|전달|말씀)해\s*주(?:세요|시기\s*바랍니다)"
)

CACHE_REUSE_THRESHOLD = 0.93
CACHE_SIMILAR_HINT_THRESHOLD = 0.7
SIMILAR_CANDIDATE_LIMIT = 60
FALLBACK_ERROR_MESSAGE = "멘트 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
WORKFLOW_ACTION_SEED_SESSION_KEY = "workflow_action_seeds"


def _request_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _apply_workspace_cache_headers(response):
    response["Cache-Control"] = "private, no-cache, must-revalidate"
    response["Pragma"] = "no-cache"
    return response


def _apply_sensitive_cache_headers(response):
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


def _result_defaults():
    return {
        "result_text": "",
        "error_message": "",
        "info_message": "",
        "limit_message": "",
        "remaining_count": None,
        "daily_limit": None,
        "usage_limit_label": "",
        "similar_items": [],
        "guest_login_url": "",
        "guest_trial_completed": False,
    }


def _peek_workflow_seed(request, token, *, expected_action=""):
    token = (token or "").strip()
    if not token:
        return None
    seeds = request.session.get(WORKFLOW_ACTION_SEED_SESSION_KEY, {})
    if not isinstance(seeds, dict):
        return None
    seed = seeds.get(token)
    if not isinstance(seed, dict):
        return None
    if expected_action and seed.get("action") != expected_action:
        return None
    return seed


def _store_action_seed(request, *, action, data):
    token = secrets.token_urlsafe(16)
    seed = {
        "action": action,
        "data": data,
        "created_at": timezone.now().isoformat(),
    }
    seeds = request.session.get(WORKFLOW_ACTION_SEED_SESSION_KEY, {})
    if not isinstance(seeds, dict):
        seeds = {}
    seeds[token] = seed
    if len(seeds) > 20:
        overflow = len(seeds) - 20
        for old_key in list(seeds.keys())[:overflow]:
            seeds.pop(old_key, None)
    request.session[WORKFLOW_ACTION_SEED_SESSION_KEY] = seeds
    request.session.modified = True
    return token


def _build_workflow_origin(request):
    return {
        "origin_service": "noticegen",
        "origin_url": request.build_absolute_uri(reverse("noticegen:main")),
        "origin_label": "안내문 멘트 생성기로 돌아가기",
    }


def _build_followup_title(target, topic):
    return f"{TARGET_LABELS.get(target, '학급')} {TOPIC_LABELS.get(topic, '안내')}".strip()


def _build_followup_context(target, topic, length_style, keywords, result_text):
    return {
        "followup_target": target,
        "followup_topic": topic,
        "followup_length_style": length_style,
        "followup_keywords": keywords,
        "followup_result_text": result_text,
    }


def _build_consent_followup_seed_data(request, *, target, topic, keywords, result_text, length_style):
    base_title = _build_followup_title(target, topic)
    data = {
        "document_title": f"{base_title} 안내문"[:200],
        "title": f"{base_title} 동의서"[:200],
        "message": (result_text or keywords).strip()[:4000],
        "keywords": keywords[:1000],
        "length_style": length_style,
        "source_label": "안내문 멘트에서 가져온 내용을 먼저 채워두었어요.",
    }
    data.update(_build_workflow_origin(request))
    return data


def _build_signature_followup_seed_data(request, *, target, topic, keywords, result_text, length_style):
    base_title = _build_followup_title(target, topic)
    instructor = ""
    if request.user.is_authenticated:
        profile = getattr(request.user, "userprofile", None)
        instructor = (getattr(profile, "nickname", "") or request.user.get_full_name() or request.user.username or "").strip()[:100]
    data = {
        "title": f"{base_title} 확인 서명"[:200],
        "print_title": f"{base_title} 확인"[:200],
        "instructor": instructor,
        "location": "",
        "description": (result_text or keywords).strip()[:2000],
        "datetime": "",
        "length_style": length_style,
        "source_label": "안내문 멘트에서 가져온 내용을 먼저 채워두었어요.",
    }
    data.update(_build_workflow_origin(request))
    return data


def _get_service():
    service = Product.objects.filter(launch_route_name="noticegen:main").first()
    if service:
        return service
    return Product.objects.filter(title=SERVICE_TITLE).first()


def _build_page_context(*, prefill=None):
    prefill = prefill or {}
    target = (prefill.get("target") or "").strip()
    topic = (prefill.get("topic") or "").strip()
    length_style = (prefill.get("length_style") or "").strip()
    keywords = (prefill.get("keywords") or "").strip()
    source_label = (prefill.get("source_label") or "").strip()
    context_values = _normalize_context_values(prefill.get("contexts") or [])

    if target not in TARGET_LABELS:
        target = DEFAULT_TARGET
    if topic not in TOPIC_LABELS:
        topic = DEFAULT_TOPIC
    if length_style not in LENGTH_LABELS:
        length_style = DEFAULT_LENGTH_STYLE

    return {
        "service": _get_service(),
        "target_options": TARGET_CHOICES,
        "topic_options": TOPIC_CHOICES,
        "context_options": CONTEXT_CHOICES,
        "length_options": LENGTH_CHOICES,
        "initial_target": target,
        "initial_topic": topic,
        "initial_length_style": length_style,
        "initial_context_values": context_values,
        "initial_keywords": keywords,
        "prefill_source_label": source_label,
        "prefill_origin_url": (prefill.get("origin_url") or "").strip(),
        "prefill_origin_label": (prefill.get("origin_label") or "").strip(),
    }


def _ensure_session_key(request):
    if request.user.is_authenticated:
        return ""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ""


def _daily_limit(request):
    return 10 if request.user.is_authenticated else 2


def _usage_limit_label(request):
    return "오늘 남은 생성 횟수" if request.user.is_authenticated else "남은 체험"


def _guest_login_continue_url():
    noticegen_url = reverse("noticegen:main")
    login_url = reverse("account_login")
    return f"{login_url}?{urlencode({'next': noticegen_url})}"


def _noticegen_ratelimit_key(group, request):
    if request.user.is_authenticated:
        return f"user:{request.user.id}"
    session_key = _ensure_session_key(request) or "anonymous"
    return f"session:{session_key}:{_request_client_ip(request) or 'unknown'}"


def _is_generation_rate_limited(request):
    return is_ratelimited(
        request=request,
        group="noticegen_generate",
        key=_noticegen_ratelimit_key,
        rate="30/10m",
        method="POST",
        increment=True,
    )


def _usage_count_today(request):
    qs = NoticeGenerationAttempt.objects.filter(charged=True)
    if request.user.is_authenticated:
        return qs.filter(user=request.user, created_at__date=timezone.localdate()).count()
    session_key = _ensure_session_key(request)
    return qs.filter(user__isnull=True, session_key=session_key).count()


def _remaining_count(request):
    limit = _daily_limit(request)
    used = _usage_count_today(request)
    return max(limit - used, 0)


def _build_usage_context(request):
    remaining_count = _remaining_count(request)
    guest_trial_completed = (not request.user.is_authenticated) and remaining_count <= 0
    return {
        "remaining_count": remaining_count,
        "daily_limit": _daily_limit(request),
        "usage_limit_label": _usage_limit_label(request),
        "guest_login_url": _guest_login_continue_url() if guest_trial_completed else "",
        "guest_trial_completed": guest_trial_completed,
    }


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
    allowed = {value for value, _label in CONTEXT_CHOICES}
    cleaned = []
    seen = set()
    for value in raw_values:
        if value in allowed and value not in seen:
            cleaned.append(value)
            seen.add(value)
    return cleaned


def _dedupe_preserve_order(values):
    cleaned = []
    seen = set()
    for value in values:
        compact = _compact_text(value)
        if not compact or compact in seen:
            continue
        seen.add(compact)
        cleaned.append(value)
    return cleaned


def _clean_keyword_fragment(value):
    value = BULLET_PREFIX_RE.sub("", value or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ,;/")


def _split_keyword_fragments(value):
    text = (value or "").replace("\r", "\n")
    fragments = []
    for chunk in FRAGMENT_SPLIT_RE.split(text):
        cleaned = _clean_keyword_fragment(chunk)
        if len(cleaned) >= 2:
            fragments.append(cleaned)
    if not fragments:
        cleaned = _clean_keyword_fragment(text)
        if cleaned:
            fragments.append(cleaned)
    return _dedupe_preserve_order(fragments)


def _normalize_keyword_prompt_text(value):
    fragments = _split_keyword_fragments(value)
    return ", ".join(fragments) if fragments else _normalize_text(value)


def _extract_explicit_details(value):
    value = value or ""
    details = []
    details.extend(match.group(0).strip() for match in EXPLICIT_DATE_PATTERN.finditer(value))
    details.extend(match.group(0).strip() for match in EXPLICIT_TIME_PATTERN.finditer(value))
    details.extend(match.group(0).strip() for match in LOCATION_PATTERN.finditer(value))
    return _dedupe_preserve_order(details)


def _infer_target_from_keywords(raw_keywords, selected_target):
    if selected_target in TARGET_LABELS:
        return selected_target
    text = _normalize_text(raw_keywords)
    if LOW_GRADE_HINT_RE.search(text):
        return TARGET_LOW
    if HIGH_GRADE_HINT_RE.search(text):
        return TARGET_HIGH
    if selected_target in TARGET_LABELS:
        return selected_target
    return DEFAULT_TARGET


def _infer_topic_from_keywords(raw_keywords, selected_topic):
    if selected_topic in TOPIC_LABELS:
        return selected_topic
    text = _normalize_text(raw_keywords)
    for inferred_topic, pattern in TOPIC_HINT_PATTERNS:
        if pattern.search(text):
            return inferred_topic
    return DEFAULT_TOPIC


def _infer_length_style(raw_keywords, selected_length_style):
    if selected_length_style in LENGTH_LABELS:
        return selected_length_style
    text = _normalize_text(raw_keywords)
    if SHORT_LENGTH_HINT_RE.search(text):
        return LENGTH_SHORT
    if LONG_LENGTH_HINT_RE.search(text):
        return LENGTH_LONG
    return DEFAULT_LENGTH_STYLE


def _infer_context_values(raw_keywords, context_values, topic):
    text = _normalize_text(raw_keywords)
    inferred = list(context_values)
    for value, pattern in CONTEXT_HINT_PATTERNS.items():
        if pattern.search(text):
            inferred.append(value)
    if topic == TOPIC_EVENT:
        inferred.append("event_notice")
    return _normalize_context_values(inferred)


def _extract_required_terms(raw_keywords):
    terms = _extract_explicit_details(raw_keywords)
    text = raw_keywords or ""
    for keyword in IMPORTANT_TERM_KEYWORDS:
        if keyword in text:
            terms.append(keyword)
    return _dedupe_preserve_order(terms)[:6]


def _prepare_generation_inputs(request):
    raw_target = (request.POST.get("target") or "").strip()
    raw_topic = (request.POST.get("topic") or "").strip()
    raw_keywords = (request.POST.get("keywords") or "").strip()
    raw_length_style = (request.POST.get("length_style") or "").strip()
    manual_context_values = _normalize_context_values(request.POST.getlist("contexts"))

    normalized_keywords = _normalize_keyword_prompt_text(raw_keywords)
    target = _infer_target_from_keywords(raw_keywords, raw_target)
    topic = _infer_topic_from_keywords(raw_keywords, raw_topic)
    length_style = _infer_length_style(raw_keywords, raw_length_style)
    context_values = _infer_context_values(raw_keywords, manual_context_values, topic)

    return {
        "target": target,
        "topic": topic,
        "keywords": raw_keywords,
        "normalized_keywords": normalized_keywords,
        "length_style": length_style,
        "manual_context_values": manual_context_values,
        "context_values": context_values,
        "required_terms": _extract_required_terms(raw_keywords),
    }


def _build_cache_key_data(target, topic, tone, keywords, context_values, length_style=LENGTH_MEDIUM):
    length_norm = length_style if length_style in LENGTH_LABELS else LENGTH_MEDIUM
    keywords_norm = _normalize_text(keywords)
    context_norm = "|".join(context_values)
    signature = f"{PROMPT_VERSION}|{target}|{topic}|{tone}|{length_norm}|{keywords_norm}|{context_norm}"
    key_hash = hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return {
        "length_style": length_norm,
        "keywords_norm": keywords_norm,
        "context_norm": context_norm,
        "signature": signature,
        "key_hash": key_hash,
    }


def _compact_text(value):
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", (value or "").lower())


def _keyword_similarity_score(left_keywords, right_keywords):
    left_compact = _compact_text(left_keywords)
    right_compact = _compact_text(right_keywords)
    if not left_compact or not right_compact:
        return 0.0
    if left_compact == right_compact:
        return 1.0

    compact_score = SequenceMatcher(None, left_compact, right_compact).ratio()
    surface_score = SequenceMatcher(None, left_keywords, right_keywords).ratio()
    if len(left_compact) >= 6 and len(right_compact) >= 6 and (
        left_compact in right_compact or right_compact in left_compact
    ):
        compact_score = min(1.0, compact_score + 0.05)
    return max(compact_score, surface_score)


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


def _collect_similar_caches(target, topic, tone, length_style, keywords_norm, context_norm):
    prefix = f"{PROMPT_VERSION}|{target}|{topic}|{tone}|{length_style}|"
    candidates = NoticeGenerationCache.objects.filter(
        target=target,
        topic=topic,
        tone=tone,
        prompt_version=PROMPT_VERSION,
        signature__startswith=prefix,
    ).order_by("-last_used_at")[:SIMILAR_CANDIDATE_LIMIT]

    scored = []
    for item in candidates:
        if (item.context_norm or "") != context_norm:
            continue
        score = _keyword_similarity_score(keywords_norm, item.keywords_norm)
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
        cleaned = BULLET_PREFIX_RE.sub("", raw_line).strip()
        if cleaned:
            lines.append(cleaned)

    if not lines:
        return ""

    compact = " ".join(lines)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact


def _missing_required_terms(result_text, required_terms):
    normalized_output = _compact_text(result_text)
    missing = []
    for term in required_terms:
        compact_term = _compact_text(term)
        if compact_term and compact_term not in normalized_output:
            missing.append(term)
    return missing


def _find_unverified_output_details(result_text, source_keywords):
    input_details = {_compact_text(item) for item in _extract_explicit_details(source_keywords)}
    unverified = []
    for item in _extract_explicit_details(result_text):
        compact_item = _compact_text(item)
        if compact_item and compact_item not in input_details:
            unverified.append(item)
    return _dedupe_preserve_order(unverified)


def _has_suspicious_output(result_text):
    if len(_compact_text(result_text)) < 20:
        return True
    if any(snippet in result_text for snippet in SUSPICIOUS_OUTPUT_SNIPPETS):
        return True
    sentences = [
        _compact_text(chunk)
        for chunk in re.split(r"[.!?]\s*", result_text)
        if _compact_text(chunk)
    ]
    if len(sentences) > 1 and len(sentences) != len(set(sentences)):
        return True
    return False


def _has_length_issue(result_text, length_style):
    rule = LENGTH_RULES.get(length_style, LENGTH_RULES[LENGTH_MEDIUM])
    minimum_chars = int(rule.get("min_chars") or 0)
    return len((result_text or "").strip()) < minimum_chars


def _has_parent_meta_instruction(result_text):
    return bool(PARENT_META_INSTRUCTION_RE.search(result_text or ""))


def _collect_output_quality_issues(result_text, source_keywords, required_terms, *, target, length_style):
    issues = []
    if _has_suspicious_output(result_text):
        issues.append("SUSPICIOUS_OUTPUT")

    if _has_length_issue(result_text, length_style):
        issues.append(f"TOO_SHORT:{length_style}")

    if target == TARGET_PARENT and _has_parent_meta_instruction(result_text):
        issues.append("PARENT_META_INSTRUCTION")

    missing_terms = _missing_required_terms(result_text, required_terms)
    if missing_terms:
        issues.append(f"MISSING_TERMS:{', '.join(missing_terms[:3])}")

    unverified_details = _find_unverified_output_details(result_text, source_keywords)
    if unverified_details:
        issues.append(f"UNVERIFIED_DETAILS:{', '.join(unverified_details[:3])}")

    return issues


def _build_retry_user_prompt(user_prompt, issues, *, target, length_style, result_text):
    correction_lines = []
    if any(issue.startswith("TOO_SHORT:") for issue in issues):
        length_rule = LENGTH_RULES.get(length_style, LENGTH_RULES[LENGTH_MEDIUM])
        correction_lines.append(
            f"- 너무 짧음. 최소 {length_rule.get('min_chars', 0)}자, {length_rule['sentence_range']}."
        )
    if target == TARGET_PARENT and "PARENT_META_INSTRUCTION" in issues:
        correction_lines.append(
            "- 학부모 직접 안내문으로. 안내해 주세요/전달해 주세요/지도해 주세요 금지."
        )
    for issue in issues:
        if issue.startswith("MISSING_TERMS:"):
            correction_lines.append(f"- 누락 포함: {issue.split(':', 1)[1]}.")
        if issue.startswith("UNVERIFIED_DETAILS:"):
            correction_lines.append(f"- 입력에 없는 정보 제거: {issue.split(':', 1)[1]}.")
    if not correction_lines:
        return user_prompt
    return (
        user_prompt
        + "\n\n직전:\n"
        + result_text
        + "\n\n수정:\n"
        + "\n".join(correction_lines)
    )


def _generate_validated_result(system_prompt, user_prompt, source_keywords, required_terms, *, target, length_style):
    last_result_text = ""
    active_user_prompt = user_prompt
    for attempt_index in range(2):
        raw_output = _call_deepseek(system_prompt, active_user_prompt)
        result_text = _sanitize_output_text(raw_output)
        if not result_text:
            if attempt_index == 0:
                logger.info("[NoticeGen] retry after empty output")
                continue
            raise RuntimeError("EMPTY_OUTPUT")

        issues = _collect_output_quality_issues(
            result_text,
            source_keywords,
            required_terms,
            target=target,
            length_style=length_style,
        )
        if not issues:
            return result_text

        last_result_text = result_text
        if attempt_index == 0:
            logger.info("[NoticeGen] retry after output quality check | issues=%s", ", ".join(issues))
            active_user_prompt = _build_retry_user_prompt(
                user_prompt,
                issues,
                target=target,
                length_style=length_style,
                result_text=result_text,
            )

    return last_result_text


def _render_result(request, payload, *, status=200):
    context = _result_defaults()
    context.update(payload)

    if request.headers.get("HX-Request") == "true":
        response = render(request, "noticegen/partials/result_panel.html", context, status=status)
        return _apply_sensitive_cache_headers(response)

    page_context = _build_page_context()
    page_context.update(context)
    response = render(request, "noticegen/main.html", page_context, status=status)
    return _apply_sensitive_cache_headers(response)


def _render_mini_result(request, payload, *, status=200):
    state_status = "success" if payload.get("result_text") else "error" if status >= 400 or payload.get("error_message") or payload.get("limit_message") else "idle"
    if state_status == "success":
        message = ""
    else:
        message = (
            payload.get("error_message")
            or payload.get("limit_message")
            or "대상과 전달 사항을 적으면 바로 복사할 문장이 나옵니다."
        )
    response = render(
        request,
        "noticegen/partials/mini_result_panel.html",
        {
            "state_status": state_status,
            "state_message": message,
            "result_text": payload.get("result_text", ""),
            "form_id": "home-mini-noticegen-form",
            "guest_login_url": payload.get("guest_login_url", ""),
        },
        status=status,
    )
    return _apply_sensitive_cache_headers(response)


def main(request):
    prefill = {}
    seed_token = (request.GET.get("sb_seed") or "").strip()
    seed = _peek_workflow_seed(request, seed_token, expected_action="notice")
    if isinstance(seed, dict):
        seed_data = seed.get("data", {}) if isinstance(seed.get("data"), dict) else {}
        prefill = {
            "target": seed_data.get("target"),
            "topic": seed_data.get("topic"),
            "length_style": seed_data.get("length_style"),
            "keywords": seed_data.get("keywords"),
            "contexts": seed_data.get("contexts") or [],
            "source_label": (seed_data.get("source_label") or "이전에 정리한 내용을 넣어두었어요."),
            "origin_url": seed_data.get("origin_url"),
            "origin_label": seed_data.get("origin_label"),
        }
    else:
        prefill = {
            "target": request.GET.get("target"),
            "topic": request.GET.get("topic"),
            "length_style": request.GET.get("length_style"),
            "keywords": request.GET.get("keywords"),
            "contexts": request.GET.getlist("contexts"),
            "source_label": "미리 입력된 내용을 확인해 주세요." if request.GET.get("keywords") else "",
            "origin_url": request.GET.get("origin_url"),
            "origin_label": request.GET.get("origin_label"),
        }

    context = _build_page_context(prefill=prefill)
    context.update(_result_defaults())
    context.update(_build_usage_context(request))
    context.update(build_noticegen_page_seo(request).as_context())
    response = render(request, "noticegen/main.html", context)
    return _apply_workspace_cache_headers(response)


def _generate_notice_payload(request):
    if _is_generation_rate_limited(request):
        logger.warning(
            "[NoticeGen] burst rate limit exceeded | user_id=%s | ip=%s",
            getattr(request.user, "id", None) if request.user.is_authenticated else None,
            _request_client_ip(request),
        )
        return 429, {
            "limit_message": "짧은 시간에 생성 요청이 많았습니다. 잠시 후 다시 시도해 주세요.",
            **_build_usage_context(request),
        }

    generation_inputs = _prepare_generation_inputs(request)
    target = generation_inputs["target"]
    topic = generation_inputs["topic"]
    keywords = generation_inputs["keywords"]
    normalized_keywords = generation_inputs["normalized_keywords"]
    length_style = generation_inputs["length_style"]
    manual_context_values = generation_inputs["manual_context_values"]
    context_values = generation_inputs["context_values"]
    required_terms = generation_inputs["required_terms"]

    if len(normalized_keywords) < 2:
        tone = get_tone_for_target(target)
        _record_attempt(
            request,
            target=target if target in TARGET_LABELS else DEFAULT_TARGET,
            topic=topic if topic in TOPIC_LABELS else DEFAULT_TOPIC,
            tone=tone,
            status=NoticeGenerationAttempt.STATUS_VALIDATION_FAIL,
            charged=False,
            error_code="INVALID_INPUT",
        )
        return 400, {
            "error_message": "전달 사항을 2글자 이상 적어 주세요.",
        }

    tone = get_tone_for_target(target)
    key_data = _build_cache_key_data(target, topic, tone, normalized_keywords, manual_context_values, length_style)
    key_hash = key_data["key_hash"]

    if (not request.user.is_authenticated) and _usage_count_today(request) >= _daily_limit(request):
        _record_attempt(
            request,
            target=target,
            topic=topic,
            tone=tone,
            status=NoticeGenerationAttempt.STATUS_LIMIT_BLOCKED,
            charged=False,
            key_hash=key_hash,
            error_code="GUEST_TRIAL_REACHED",
        )
        return 429, {
            "limit_message": "비회원 체험 2회를 모두 사용했습니다. 로그인 후 계속 쓸 수 있습니다.",
            **_build_usage_context(request),
        }

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
        return 200, {
            "result_text": exact_cache.result_text,
            **_build_usage_context(request),
        }

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
        if request.user.is_authenticated:
            limit_message = f"오늘 멘트 생성 횟수({_daily_limit(request)}회)를 모두 사용했습니다."
        else:
            limit_message = "비회원 체험 2회를 모두 사용했습니다. 로그인 후 계속 쓸 수 있습니다."
        return 429, {
            "limit_message": limit_message,
            **_build_usage_context(request),
        }

    similar_scored = _collect_similar_caches(
        target,
        topic,
        tone,
        key_data["length_style"],
        key_data["keywords_norm"],
        key_data["context_norm"],
    )
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
        return 200, {
            "result_text": reused_cache.result_text,
            "similar_items": similar_items,
            **_build_usage_context(request),
        }

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
    system_prompt = build_system_prompt(target, key_data["length_style"])
    user_prompt = build_user_prompt(target, topic, normalized_keywords, context_text, key_data["length_style"])

    try:
        result_text = _generate_validated_result(
            system_prompt,
            user_prompt,
            normalized_keywords,
            required_terms,
            target=target,
            length_style=key_data["length_style"],
        )
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
        return 200, {
            "error_message": FALLBACK_ERROR_MESSAGE,
            "similar_items": similar_items,
            **_build_usage_context(request),
        }

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
    return 200, {
        "result_text": result_text,
        "similar_items": similar_items,
        **_build_usage_context(request),
    }


@require_POST
def generate_notice(request):
    status, payload = _generate_notice_payload(request)
    return _render_result(request, payload, status=status)


@require_POST
def generate_notice_mini(request):
    status, payload = _generate_notice_payload(request)
    return _render_mini_result(request, payload, status=status)


@login_required
@require_POST
def start_consent_followup(request):
    target = (request.POST.get("target") or "").strip()
    topic = (request.POST.get("topic") or "").strip()
    keywords = (request.POST.get("keywords") or "").strip()
    result_text = (request.POST.get("result_text") or "").strip()
    length_style = (request.POST.get("length_style") or LENGTH_MEDIUM).strip()
    seed_token = _store_action_seed(
        request,
        action="consent",
        data=_build_consent_followup_seed_data(
            request,
            target=target,
            topic=topic,
            keywords=keywords,
            result_text=result_text,
            length_style=length_style,
        ),
    )
    return redirect(f"{reverse('consent:create_step1')}?sb_seed={seed_token}")


@login_required
@require_POST
def start_signature_followup(request):
    target = (request.POST.get("target") or "").strip()
    topic = (request.POST.get("topic") or "").strip()
    keywords = (request.POST.get("keywords") or "").strip()
    result_text = (request.POST.get("result_text") or "").strip()
    length_style = (request.POST.get("length_style") or LENGTH_MEDIUM).strip()
    seed_token = _store_action_seed(
        request,
        action="signature",
        data=_build_signature_followup_seed_data(
            request,
            target=target,
            topic=topic,
            keywords=keywords,
            result_text=result_text,
            length_style=length_style,
        ),
    )
    return redirect(f"{reverse('signatures:create')}?sb_seed={seed_token}")
