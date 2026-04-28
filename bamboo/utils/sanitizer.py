from __future__ import annotations

import re
from dataclasses import dataclass

MASK_TOKEN = "[●●●]"


@dataclass(frozen=True)
class SanitizedText:
    raw_text: str
    masked_text: str
    redacted_values: tuple[str, ...]


PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?82[-.\s]?)?(?:0\d{1,2}[-.\s]?)?\d{3,4}[-.\s]?\d{4}(?!\d)"
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
GRADE_CLASS_RE = re.compile(r"(?<!\d)\d{1,2}\s*학년\s*\d{1,2}\s*반|(?<!\d)\d{1,2}\s*-\s*\d{1,2}\s*반")
DATE_RE = re.compile(r"(?<!\d)\d{1,2}\s*월\s*\d{1,2}\s*일|(?<!\d)\d{4}\s*년\s*\d{1,2}\s*월|(?<!\d)\d{1,2}\s*/\s*\d{1,2}(?!\d)")
SCHOOL_RE = re.compile(
    r"[가-힣A-Za-z0-9]{1,24}(?:초등학교|중학교|고등학교|특수학교|국제학교|학교|유치원|어린이집|교육청|교육지원청)"
)
REGION_RE = re.compile(
    r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
    r"(?:특별시|광역시|특별자치시|특별자치도|도)?|"
    r"[가-힣]{2,12}(?:시|군|구|읍|면|동)"
)
NAME_TITLE_RE = re.compile(
    r"[가-힣]{2,4}\s*(?:선생님|교장|교감|원장|부장|실장|행정실장|학부모|담임|관리자|주무관)(?:이|가|은|는|을|를|께서)?"
)
TITLE_NAME_RE = re.compile(
    r"(?:선생님|교장|교감|원장|부장|실장|행정실장|학부모|담임|관리자|주무관)\s*[가-힣]{2,4}(?:이|가|은|는|을|를|께서)?"
)
ROOM_RE = re.compile(r"(?<!\d)\d{1,2}\s*(?:반|학급|교실)")

PATTERNS = (
    EMAIL_RE,
    PHONE_RE,
    SCHOOL_RE,
    NAME_TITLE_RE,
    TITLE_NAME_RE,
    GRADE_CLASS_RE,
    DATE_RE,
    ROOM_RE,
    REGION_RE,
)


def sanitize_input(text: str) -> SanitizedText:
    raw_text = normalize_input(text)
    masked_text = raw_text
    redacted: list[str] = []

    for pattern in PATTERNS:
        masked_text = pattern.sub(lambda match: _mask_match(match, redacted), masked_text)

    masked_text = re.sub(rf"(?:\s*{re.escape(MASK_TOKEN)}\s*)+", f" {MASK_TOKEN} ", masked_text)
    masked_text = re.sub(r"\s+", " ", masked_text).strip()
    return SanitizedText(raw_text=raw_text, masked_text=masked_text, redacted_values=tuple(_dedupe(redacted)))


def normalize_input(text: str) -> str:
    normalized = str(text or "").replace("\u200b", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized[:200]


def extract_input_identifiers(text: str) -> tuple[str, ...]:
    values: list[str] = []
    normalized = normalize_input(text)
    for pattern in PATTERNS:
        values.extend(match.group(0).strip() for match in pattern.finditer(normalized))
    return tuple(_dedupe(values))


def _mask_match(match, redacted: list[str]) -> str:
    value = match.group(0).strip()
    if value:
        redacted.append(value)
    return MASK_TOKEN


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        compact = re.sub(r"\s+", "", value)
        if not compact or compact in seen:
            continue
        seen.add(compact)
        result.append(value)
    return result
