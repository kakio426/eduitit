from __future__ import annotations

import re

SAFE_EXPRESSION_TOKEN = "[표현 순화]"

SEXUAL_CONTENT_RE = re.compile(
    r"섹스|성관계|자위|포르노|야동|음란|성기|강간|성폭행|성추행|성희롱|"
    r"슴가|엉덩이|알몸|나체|벗기|빨가벗|19금|야한\s*말|성적\s*농담|성적\s*묘사|"
    r"가슴\s*(?:만지|보여|봤|노출)"
)
STRONG_PROFANITY_RE = re.compile(
    r"씨\s*발|시\s*발|ㅅ\s*ㅂ|개\s*새끼|병\s*신|좆|존\s*나|"
    r"지랄|꺼져|엿\s*같|미친\s*(?:놈|년|새끼)|또라이|쓰레기|년놈"
)
HATE_OR_BODY_INSULT_RE = re.compile(
    r"장애인\s*같|정신병자|미개한|외모\s*비하|돼지\s*같|못생긴|"
    r"가족\s*욕|애미|애비"
)

PUBLIC_UNSAFE_EXPRESSION_RE = re.compile(
    "|".join(
        f"(?:{pattern.pattern})"
        for pattern in (SEXUAL_CONTENT_RE, STRONG_PROFANITY_RE, HATE_OR_BODY_INSULT_RE)
    )
)


def mask_public_unsafe_expressions(text: str) -> tuple[str, tuple[str, ...]]:
    values: list[str] = []

    def replace(match: re.Match) -> str:
        value = match.group(0).strip()
        if value:
            values.append(value)
        return SAFE_EXPRESSION_TOKEN

    masked = PUBLIC_UNSAFE_EXPRESSION_RE.sub(replace, text or "")
    return masked, tuple(_dedupe(values))


def contains_public_unsafe_expression(text: str) -> bool:
    return bool(PUBLIC_UNSAFE_EXPRESSION_RE.search(text or ""))


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
