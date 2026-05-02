import re
import uuid

from seed_quiz.models import SQGamePlayer


BLOCKED_TERMS = {
    "ㅅㅂ",
    "시발",
    "씨발",
    "병신",
    "미친놈",
    "미친년",
    "개새",
    "꺼져",
    "좆",
    "지랄",
    "fuck",
    "shit",
}


def _result(ok: bool, code: str = "", message: str = "") -> dict:
    return {"ok": ok, "code": code, "message": message}


def _compact(value: str) -> str:
    return re.sub(r"[\W_]+", "", str(value or "").lower(), flags=re.UNICODE)


def _same_request_id(left, right) -> bool:
    if not left or not right:
        return False
    try:
        return uuid.UUID(str(left)) == uuid.UUID(str(right))
    except (TypeError, ValueError, AttributeError):
        return False


def _has_noise_pattern(text: str) -> bool:
    compact = _compact(text)
    if not compact:
        return True
    if re.search(r"(.)\1{7,}", compact):
        return True
    unique_chars = set(compact)
    return len(compact) >= 10 and len(unique_chars) <= 2


def _has_blocked_term(*values: str) -> bool:
    compact = _compact(" ".join(values))
    return any(term in compact for term in BLOCKED_TERMS)


def prefilter_question_submission(
    *,
    player: SQGamePlayer,
    question_text: str,
    answer_text: str = "",
    choices: list[str] | None = None,
    request_id=None,
) -> dict:
    question = str(question_text or "").strip()
    answer = str(answer_text or "").strip()
    clean_choices = [str(choice or "").strip() for choice in (choices or []) if str(choice or "").strip()]

    if len(question) < 5:
        return _result(False, "question_too_short", "문제를 조금 더 분명하게 적어 주세요.")
    if len(question) > 180:
        return _result(False, "question_too_long", "문제를 짧게 줄여 주세요.")
    if answer and len(answer) > 80:
        return _result(False, "answer_too_long", "정답을 짧게 줄여 주세요.")
    if _has_noise_pattern(question):
        return _result(False, "noise", "문제 문장을 다시 다듬어 주세요.")
    if _has_blocked_term(question, answer, *clean_choices):
        return _result(False, "blocked_term", "표현을 다시 다듬어 주세요.")

    normalized_question = _compact(question)
    existing_questions = player.authored_questions.exclude(status="rejected").only("question_text", "request_id")
    for existing in existing_questions:
        if _same_request_id(existing.request_id, request_id):
            continue
        if _compact(existing.question_text) == normalized_question:
            return _result(False, "duplicate_question", "이미 만든 문제예요.")

    return _result(True)
