import re
import unicodedata

FORBIDDEN_CHARS = "\ufffd"  # 깨진 문자
MAX_Q_LEN = 120
MAX_C_LEN = 40
MAX_E_LEN = 200


def normalize_and_check(text: str) -> str:
    """NFC 정규화 + 깨진 문자/HTML 태그/제어 문자 제거."""
    norm = unicodedata.normalize("NFC", text.strip())
    if FORBIDDEN_CHARS in norm:
        raise ValueError("Broken character in text")
    norm = re.sub(r"<[^>]+>", "", norm)  # HTML 태그 제거
    norm = re.sub(r"[\x00-\x1f\x7f]", "", norm)  # 제어문자 제거
    return norm


def validate_quiz_payload(payload: dict) -> tuple[bool, list[str]]:
    """
    AI/폴백에서 받은 payload를 검증한다.
    반환: (is_valid, error_codes)
    """
    errors: list[str] = []
    items = payload.get("items", [])

    if len(items) != 3:
        errors.append("item_count_not_3")
        return False, errors  # 이후 검증 불가

    for idx, item in enumerate(items, start=1):
        # 텍스트 정규화 시도
        try:
            q = normalize_and_check(item.get("question_text", ""))
            choices_raw = item.get("choices", [])
            choices = [normalize_and_check(c) for c in choices_raw]
        except ValueError:
            errors.append(f"q{idx}_broken_char")
            continue

        correct = item.get("correct_index")
        explanation = item.get("explanation", "")

        # 문제 검증
        if not q or len(q) > MAX_Q_LEN:
            errors.append(f"q{idx}_question_length")

        # 선택지 검증
        if len(choices) != 4:
            errors.append(f"q{idx}_choices_not_4")
        else:
            if any(not c for c in choices):
                errors.append(f"q{idx}_empty_choice")
            if len(set(choices)) != 4:
                errors.append(f"q{idx}_duplicate_choice")
            if any(len(c) > MAX_C_LEN for c in choices):
                errors.append(f"q{idx}_choice_too_long")

        # 정답 인덱스 검증
        if correct not in [0, 1, 2, 3]:
            errors.append(f"q{idx}_invalid_correct_index")

        # 해설 검증 (선택)
        if explanation and len(explanation) > MAX_E_LEN:
            errors.append(f"q{idx}_explanation_too_long")

    return len(errors) == 0, errors
