from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence

from django.core.cache import cache
from django.utils import timezone

AIUsageLimit = tuple[int, int]
AIUsageScope = tuple[str, str, Sequence[AIUsageLimit]]


def user_usage_subject(user) -> str:
    user_id = getattr(user, "id", None) or "anonymous"
    joined = getattr(user, "date_joined", None)
    joined_part = joined.isoformat() if joined else ""
    if joined_part:
        return f"user:{user_id}:{joined_part}"
    return f"user:{user_id}"


def consume_ai_usage_limit(bucket: str, subject: str, limits: Sequence[AIUsageLimit]) -> bool:
    return consume_ai_usage_limits([(bucket, subject, limits)])


def consume_ai_usage_limits(scopes: Iterable[AIUsageScope]) -> bool:
    entries = []
    now = timezone.now()
    for bucket, subject, limits in scopes:
        for window_seconds, max_count in _normalize_limits(limits):
            if max_count <= 0:
                return True
            cache_key = _cache_key(bucket=bucket, subject=subject, window_seconds=window_seconds, now=now)
            timeout = int(window_seconds) + 60
            entries.append((cache_key, timeout, max_count))

    for cache_key, _timeout, max_count in entries:
        if _current_count(cache_key) >= max_count:
            return True

    for cache_key, timeout, _max_count in entries:
        _increment_count(cache_key, timeout=timeout)
    return False


def _normalize_limits(limits: Sequence[AIUsageLimit]) -> list[AIUsageLimit]:
    normalized = []
    for raw_window, raw_max_count in limits or ():
        try:
            window_seconds = int(raw_window)
            max_count = int(raw_max_count)
        except (TypeError, ValueError):
            continue
        if window_seconds <= 0:
            continue
        normalized.append((window_seconds, max_count))
    return normalized


def _cache_key(*, bucket: str, subject: str, window_seconds: int, now) -> str:
    bucket_part = re.sub(r"[^A-Za-z0-9_.:-]+", "_", str(bucket or "ai")).strip("_")[:80] or "ai"
    subject_hash = hashlib.sha256(str(subject or "unknown").encode("utf-8")).hexdigest()[:32]
    if window_seconds >= 86400:
        slot = timezone.localtime(now).date().isoformat()
    else:
        slot = int(now.timestamp()) // int(window_seconds)
    return f"ai-usage:{bucket_part}:{window_seconds}:{slot}:{subject_hash}"


def _current_count(cache_key: str) -> int:
    current = cache.get(cache_key) or 0
    try:
        return max(int(current), 0)
    except (TypeError, ValueError):
        return 0


def _increment_count(cache_key: str, *, timeout: int) -> int:
    current = cache.get(cache_key)
    if current is None:
        cache.set(cache_key, 1, timeout=timeout)
        return 1
    try:
        return int(cache.incr(cache_key))
    except Exception:
        next_value = _current_count(cache_key) + 1
        cache.set(cache_key, next_value, timeout=timeout)
        return next_value
