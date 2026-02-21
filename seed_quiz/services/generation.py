import json
import logging
import os

from django.db import transaction
from django.utils import timezone

from seed_quiz.data.fallback_loader import load_fallback_bank
from seed_quiz.models import SQGenerationLog, SQQuizItem, SQQuizSet
from seed_quiz.services.validator import normalize_and_check, validate_quiz_payload

logger = logging.getLogger("seed_quiz.generation")

# AI 설정 (타임아웃 5초, 재시도 1회 → 최대 총 ~10초)
AI_TIMEOUT = 5.0
AI_RETRIES = 1

PRESET_LABELS = {
    "general": "상식",
    "math": "수학",
    "korean": "국어",
    "science": "과학",
    "social": "사회",
    "english": "영어",
}

SYSTEM_PROMPT = """\
당신은 대한민국 초등학교 교육 전문가입니다. 교사가 요청하는 학년과 과목에 맞는 퀴즈를 만들어 주세요.
반드시 JSON 형식으로만 출력하고 다른 텍스트는 절대 포함하지 마세요."""


def _make_user_prompt(grade: int, preset_type: str) -> str:
    label = PRESET_LABELS.get(preset_type, "상식")
    return (
        f"초등학교 {grade}학년 학생을 위한 {label} 퀴즈 3문제를 JSON으로 출력하세요.\n"
        '출력 형식:\n{"items":[{"question_text":"문제","choices":["A","B","C","D"],'
        '"correct_index":0,"explanation":"해설","difficulty":"medium"}]}\n'
        f"규칙: 선택지 정확히 4개, 중복 없음, 빈 선택지 없음, 한국어만, {grade}학년 수준에 맞게."
    )


def _call_ai(grade: int, preset_type: str) -> dict:
    """DeepSeek API 호출. 실패 시 예외 발생."""
    from openai import OpenAI

    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("MASTER_DEEPSEEK_API_KEY not set")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=AI_TIMEOUT,
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _make_user_prompt(grade, preset_type)},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
    )
    return json.loads(response.choices[0].message.content)


def _create_items(quiz_set: SQQuizSet, items: list) -> None:
    for i, item in enumerate(items, start=1):
        q = normalize_and_check(item["question_text"])
        choices = [normalize_and_check(c) for c in item["choices"]]
        explanation_raw = item.get("explanation", "")
        explanation = normalize_and_check(explanation_raw) if explanation_raw else ""
        SQQuizItem.objects.create(
            quiz_set=quiz_set,
            order_no=i,
            question_text=q,
            choices=choices,
            correct_index=item["correct_index"],
            explanation=explanation,
            difficulty=item.get("difficulty", "medium"),
        )


def generate_and_save_draft(classroom, preset_type: str, grade: int, created_by) -> SQQuizSet:
    """
    AI 생성 시도 → 검증 → 실패 시 폴백.
    항상 status='draft' SQQuizSet 반환.

    동시 중복 방지:
    - get_or_create(draft)를 atomic 블록 안에서 처리
    - item 저장도 별도 atomic 블록으로 처리
    - failed 상태 저장은 outer atomic 없이 즉시 커밋
    """
    target_date = timezone.localdate()

    # quiz_set 확보 (get_or_create, atomic으로 race condition 방지)
    with transaction.atomic():
        quiz_set, created = SQQuizSet.objects.get_or_create(
            classroom=classroom,
            target_date=target_date,
            preset_type=preset_type,
            status="draft",
            defaults={
                "grade": grade,
                "title": f"{target_date} {PRESET_LABELS.get(preset_type, '상식')} 퀴즈",
                "source": "ai",
                "created_by": created_by,
            },
        )
        if not created:
            quiz_set.items.all().delete()  # 재생성: 기존 문항 삭제

    source = "ai"
    payload = None
    last_error = None

    # AI 생성 시도 (최대 AI_RETRIES + 1 회)
    for attempt_no in range(AI_RETRIES + 1):
        try:
            payload = _call_ai(grade, preset_type)
            ok, errors = validate_quiz_payload(payload)
            if ok:
                break
            raise ValueError(f"AI 검증 실패: {errors}")
        except Exception as e:
            last_error = e
            logger.warning(
                "seed_quiz AI 시도 실패 attempt=%d grade=%d preset=%s error=%s",
                attempt_no,
                grade,
                preset_type,
                str(e)[:200],
            )
            SQGenerationLog.objects.create(
                quiz_set=quiz_set,
                level="warn",
                code="AI_ATTEMPT_FAILED",
                message=str(e)[:500],
                payload={"attempt": attempt_no, "grade": grade, "preset": preset_type},
            )
            payload = None

    if payload is None:
        # 폴백 전환
        SQGenerationLog.objects.create(
            quiz_set=quiz_set,
            level="warn",
            code="FALLBACK_USED",
            message="AI 실패, 기본 문제은행으로 전환",
            payload={"error": str(last_error)[:200]},
        )
        try:
            payload = load_fallback_bank(preset_type, grade)
            ok, errors = validate_quiz_payload(payload)
            if not ok:
                raise ValueError(f"폴백 검증 실패: {errors}")
            source = "fallback"
        except Exception as fe:
            SQGenerationLog.objects.create(
                quiz_set=quiz_set,
                level="error",
                code="FALLBACK_FAILED",
                message=str(fe)[:500],
            )
            quiz_set.status = "failed"
            quiz_set.save(update_fields=["status"])
            raise RuntimeError(f"퀴즈 생성 완전 실패: {fe}") from fe

    # 문항 저장 (atomic으로 부분 저장 방지)
    with transaction.atomic():
        _create_items(quiz_set, payload["items"])
    quiz_set.source = source
    quiz_set.save(update_fields=["source"])

    SQGenerationLog.objects.create(
        quiz_set=quiz_set,
        level="info",
        code="DRAFT_CREATED",
        message=f"source={source}, items=3",
    )
    logger.info(
        "seed_quiz draft created quiz_set=%s source=%s", str(quiz_set.id), source
    )
    return quiz_set
