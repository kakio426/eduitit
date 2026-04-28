from __future__ import annotations

import re
from dataclasses import dataclass

from .sanitizer import MASK_TOKEN, extract_input_identifiers
from .safety import PUBLIC_UNSAFE_EXPRESSION_RE, SAFE_EXPRESSION_TOKEN


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    reasons: tuple[str, ...] = ()


TITLE_NAME_RE = re.compile(
    r"(?:선생님|교장|교감|원장|부장|실장|행정실장|학부모|담임|관리자|주무관)\s*[가-힣]{2,4}(?:이|가|은|는|을|를|께서)?|"
    r"[가-힣]{2,4}\s*(?:선생님|교장|교감|원장|부장|실장|행정실장|학부모|담임|관리자|주무관)(?:이|가|은|는|을|를|께서)?"
)
SCHOOL_RE = re.compile(
    r"[가-힣A-Za-z0-9]{1,24}(?:초등학교|중학교|고등학교|특수학교|국제학교|학교|유치원|어린이집|교육청|교육지원청)"
)
PHONE_OR_EMAIL_RE = re.compile(
    r"(?<!\d)(?:\+?82[-.\s]?)?(?:0\d{1,2}[-.\s]?)?\d{3,4}[-.\s]?\d{4}(?!\d)|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
GRADE_CLASS_RE = re.compile(r"(?<!\d)\d{1,2}\s*학년\s*\d{1,2}\s*반|(?<!\d)\d{1,2}\s*-\s*\d{1,2}\s*반")
THREAT_RE = re.compile(
    r"죽이|살해|패버|때려|폭행|해치|불태|묻어버|저주|고소하|소송|협박|성적\s*묘사|음란|자살|극단적\s*선택"
)
FORBIDDEN_META_RE = re.compile(r"실존|기관|학교명|이름을|마스킹|[●]{2,}")
DIRECT_INSULT_RE = re.compile(r"병신|개새끼|쓰레기|미친놈|미친년|년놈|또라이|멍청한\s*인간|인간\s*말종")
FABLE_TITLE_RE = re.compile(r"^\s*##\s*제목\s*:\s*(?P<title>[^\n]+)", re.MULTILINE)
TITLE_ROLE_RE = re.compile(r"교사|선생|교장|교감|원장|부장|실장|행정실장|학부모|담임|관리자|주무관|학생")
META_ARTIFACT_RE = re.compile(
    r"죄송|미안|사과|이전\s*출력|출력에\s*문제|지시를\s*정확히|"
    r"다시\s*쓰겠|재작성|요청하신|규칙을\s*반영|프롬프트|가이드라인"
)


def validate_fable_output(
    output: str,
    *,
    raw_input: str = "",
    masked_input: str = "",
    redacted_values: tuple[str, ...] = (),
) -> ValidationResult:
    text = (output or "").strip()
    reasons: list[str] = []

    if len(text) < 80:
        reasons.append("too_short")
    if "## 제목:" not in text or "숲의 속삭임" not in text:
        reasons.append("format")
    if not re.match(r"^\s*##\s*제목\s*:", text):
        reasons.append("preamble")
    title = extract_fable_title(text)
    reasons.extend(f"title_{reason}" for reason in validate_fable_title(title).reasons)
    if TITLE_NAME_RE.search(text):
        reasons.append("person_pattern")
    if SCHOOL_RE.search(text):
        reasons.append("school_pattern")
    if PHONE_OR_EMAIL_RE.search(text):
        reasons.append("contact_pattern")
    if GRADE_CLASS_RE.search(text):
        reasons.append("class_pattern")
    if THREAT_RE.search(text):
        reasons.append("threat_pattern")
    if DIRECT_INSULT_RE.search(text):
        reasons.append("direct_insult")
    if PUBLIC_UNSAFE_EXPRESSION_RE.search(text):
        reasons.append("unsafe_expression")
    if SAFE_EXPRESSION_TOKEN in text:
        reasons.append("unsafe_token")
    if FORBIDDEN_META_RE.search(text):
        reasons.append("prompt_artifact")
    if META_ARTIFACT_RE.search(text):
        reasons.append("meta_artifact")

    for value in _input_values_to_block(raw_input, masked_input, redacted_values):
        if value and value in text:
            reasons.append("input_identifier")
            break

    return ValidationResult(is_valid=not reasons, reasons=tuple(dict.fromkeys(reasons)))


def extract_fable_title(output: str) -> str:
    match = FABLE_TITLE_RE.search(output or "")
    if not match:
        return ""
    title = re.sub(r"\s+", " ", match.group("title") or "").strip()
    return title.strip("〈〉<> ")


def validate_fable_title(title: str) -> ValidationResult:
    text = (title or "").strip()
    reasons: list[str] = []
    if not text:
        reasons.append("missing")
    if len(text) > 80:
        reasons.append("too_long")
    if len(text) < 6:
        reasons.append("too_short")
    if TITLE_NAME_RE.search(text):
        reasons.append("person_pattern")
    if SCHOOL_RE.search(text):
        reasons.append("school_pattern")
    if PHONE_OR_EMAIL_RE.search(text):
        reasons.append("contact_pattern")
    if GRADE_CLASS_RE.search(text):
        reasons.append("class_pattern")
    if THREAT_RE.search(text):
        reasons.append("threat_pattern")
    if DIRECT_INSULT_RE.search(text):
        reasons.append("direct_insult")
    if PUBLIC_UNSAFE_EXPRESSION_RE.search(text):
        reasons.append("unsafe_expression")
    if SAFE_EXPRESSION_TOKEN in text:
        reasons.append("unsafe_token")
    if FORBIDDEN_META_RE.search(text):
        reasons.append("prompt_artifact")
    if META_ARTIFACT_RE.search(text):
        reasons.append("meta_artifact")
    if TITLE_ROLE_RE.search(text):
        reasons.append("human_role")
    return ValidationResult(is_valid=not reasons, reasons=tuple(dict.fromkeys(reasons)))


def _input_values_to_block(
    raw_input: str,
    masked_input: str,
    redacted_values: tuple[str, ...],
) -> tuple[str, ...]:
    values = list(redacted_values or ())
    values.extend(extract_input_identifiers(raw_input))
    for value in re.findall(r"[가-힣A-Za-z0-9]{2,}", raw_input or ""):
        if value and value not in (masked_input or "") and _looks_specific(value):
            values.append(value)
    cleaned = []
    seen = set()
    for value in values:
        compact = re.sub(r"\s+", "", str(value or ""))
        if len(compact) < 2 or compact == MASK_TOKEN or compact in seen:
            continue
        seen.add(compact)
        cleaned.append(compact)
    return tuple(cleaned)


def _looks_specific(value: str) -> bool:
    if re.search(r"\d", value):
        return True
    if SCHOOL_RE.search(value) or TITLE_NAME_RE.search(value):
        return True
    return False
