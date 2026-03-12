import hashlib
import hmac
import json
import os
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import FortunePseudonymousCache

CACHE_RETENTION_DAYS = 30

_LINE_BLOCK_PATTERNS = (
    re.compile(r'^\s*-?\s*생일\s*[:：].*$', re.IGNORECASE),
    re.compile(r'^\s*Birth Datetime\s*:\s*.*$', re.IGNORECASE),
    re.compile(r'^\s*-?\s*[년월일시]주\s*[:：].*$', re.IGNORECASE),
    re.compile(r'^\s*-?\s*(사주|팔자|원국|명식)\s*[:：].*$', re.IGNORECASE),
)
_INLINE_PATTERNS = (
    re.compile(r'\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일(?:\s*\([^)]*\))?(?:\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?)?'),
    re.compile(r'\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?'),
    re.compile(r'([년월일시]주)\s*[:：]?\s*[갑을병정무기경신임계][자축인묘진사오미신유술해]'),
    re.compile(r'(?:[甲乙丙丁戊己庚辛壬癸갑을병정무기경신임계][子丑寅卯辰巳午未申酉戌亥자축인묘진사오미신유술해]\s*){2,4}'),
)


def scrub_personal_fortune_text(text):
    if not text:
        return ""

    scrubbed_lines = []
    for raw_line in str(text).splitlines():
        if any(pattern.match(raw_line) for pattern in _LINE_BLOCK_PATTERNS):
            continue
        line = raw_line
        for pattern in _INLINE_PATTERNS:
            line = pattern.sub('[비공개]', line)
        scrubbed_lines.append(line)

    cleaned = "\n".join(scrubbed_lines)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return cleaned


def normalize_birth_payload(data):
    return {
        'mode': data.get('mode'),
        'gender': data.get('gender'),
        'calendar_type': data.get('calendar_type'),
        'birth_year': data.get('birth_year'),
        'birth_month': data.get('birth_month'),
        'birth_day': data.get('birth_day'),
        'birth_hour': data.get('birth_hour'),
        'birth_minute': data.get('birth_minute'),
    }


def normalize_daily_payload(mode, target_date, natal_chart):
    return {
        'mode': mode,
        'target_date': str(target_date),
        'natal_chart': natal_chart or {},
    }


def dumps_canonical_payload(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def build_user_pseudonymous_fingerprint(user_id, payload):
    secret = os.environ.get('FORTUNE_PSEUDONYM_KEY') or getattr(settings, 'SECRET_KEY', '')
    canonical = dumps_canonical_payload(payload)
    digest = hmac.new(
        secret.encode('utf-8'),
        f'{user_id}:{canonical}'.encode('utf-8'),
        hashlib.sha256,
    )
    return digest.hexdigest()


def get_cached_pseudonymous_result(user, purpose, fingerprint):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    now = timezone.now()
    return FortunePseudonymousCache.objects.filter(
        user=user,
        purpose=purpose,
        fingerprint=fingerprint,
        expires_at__gt=now,
    ).order_by('-created_at').first()


def store_cached_pseudonymous_result(user, purpose, fingerprint, result_text):
    if not user or not getattr(user, 'is_authenticated', False):
        return None

    sanitized = scrub_personal_fortune_text(result_text)
    expires_at = timezone.now() + timedelta(days=CACHE_RETENTION_DAYS)
    cache_entry, _ = FortunePseudonymousCache.objects.update_or_create(
        user=user,
        purpose=purpose,
        fingerprint=fingerprint,
        defaults={
            'result_text': sanitized,
            'expires_at': expires_at,
        },
    )
    return cache_entry
