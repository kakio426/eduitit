from __future__ import annotations

from dataclasses import dataclass

from .sanitizer import MASK_TOKEN, SanitizedText, sanitize_input
from .safety import contains_public_unsafe_expression
from .validator import DIRECT_INSULT_RE, THREAT_RE


@dataclass(frozen=True)
class CommentSafetyResult:
    is_valid: bool
    sanitized: SanitizedText
    reasons: tuple[str, ...] = ()


def sanitize_comment_body(text: str) -> CommentSafetyResult:
    sanitized = sanitize_input(text)
    reasons: list[str] = []
    if MASK_TOKEN in sanitized.masked_text:
        reasons.append("identifier")
    if THREAT_RE.search(sanitized.masked_text):
        reasons.append("threat")
    if DIRECT_INSULT_RE.search(sanitized.masked_text) or contains_public_unsafe_expression(text):
        reasons.append("direct_insult")
    return CommentSafetyResult(
        is_valid=not reasons,
        sanitized=sanitized,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def comment_error_message(result: CommentSafetyResult) -> str:
    if "identifier" in result.reasons:
        return "특정 정보는 빼고 써주세요."
    if "threat" in result.reasons:
        return "위협 표현은 쓸 수 없어요."
    if "direct_insult" in result.reasons:
        return "표현을 조금 순하게 바꿔주세요."
    return "댓글을 확인해주세요."
