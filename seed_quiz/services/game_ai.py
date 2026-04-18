import json
import math
import os
import random

from openai import OpenAI

from seed_quiz.topics import TOPIC_LABELS

AI_TIMEOUT = 5.0
AI_RETRIES = 1

DISTRACTOR_SYSTEM_PROMPT = """\
당신은 대한민국 초등학생용 객관식 문항을 다듬는 교실 도우미입니다.
반드시 JSON만 출력하세요.
"""

QUALITY_SYSTEM_PROMPT = """\
당신은 대한민국 초등 교실 문제 품질 평가자입니다.
반드시 JSON만 출력하세요.
"""


def _call_ai_json(*, system_prompt: str, user_prompt: str) -> dict:
    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("MASTER_DEEPSEEK_API_KEY not set")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=AI_TIMEOUT,
    )
    last_error = None
    for _ in range(AI_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as exc:  # pragma: no cover - network failures are mocked in tests
            last_error = exc
    raise last_error or RuntimeError("game ai call failed")


def _dedupe_choices(values: list[str], *, exclude: set[str] | None = None) -> list[str]:
    exclude = {str(item or "").strip() for item in (exclude or set()) if str(item or "").strip()}
    seen = set()
    results = []
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in exclude or value in seen:
            continue
        seen.add(value)
        results.append(value)
    return results


def _fallback_distractors(correct_answer: str) -> list[str]:
    answer = str(correct_answer or "").strip()
    if not answer:
        return ["모르겠다", "비슷한 답", "다른 답"]
    seeds = [
        f"{answer} 아님",
        f"{answer}와 비슷한 말",
        f"{answer} 반대 뜻",
        f"{answer}와 다른 예",
        "모르겠다",
        "헷갈리는 보기",
    ]
    return _dedupe_choices(seeds, exclude={answer})[:3]


def generate_distractors(*, question: str, correct_answer: str, topic: str, grade: int) -> list[str]:
    topic_label = TOPIC_LABELS.get(topic, topic)
    user_prompt = (
        f"초등학교 {grade}학년용 {topic_label} 문제입니다.\n"
        f"문제: {question}\n"
        f"정답: {correct_answer}\n"
        '다른 텍스트 없이 {"distractors":["보기1","보기2","보기3"]} 형식으로만 답하세요.\n'
        "규칙: 한국어, 정답과 중복 금지, 서로 중복 금지, 초등학생이 헷갈릴 만한 보기."
    )
    payload = _call_ai_json(
        system_prompt=DISTRACTOR_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    distractors = _dedupe_choices(payload.get("distractors") or [], exclude={correct_answer})
    if len(distractors) < 3:
        distractors = _dedupe_choices(distractors + _fallback_distractors(correct_answer), exclude={correct_answer})
    return distractors[:3]


def build_multiple_choices(
    *,
    question: str,
    correct_answer: str,
    topic: str,
    grade: int,
) -> tuple[list[str], int, bool]:
    used_fallback = False
    try:
        distractors = generate_distractors(
            question=question,
            correct_answer=correct_answer,
            topic=topic,
            grade=grade,
        )
    except Exception:
        distractors = _fallback_distractors(correct_answer)
        used_fallback = True
    choice_pool = _dedupe_choices([correct_answer, *distractors])
    if len(choice_pool) < 4:
        used_fallback = True
        choice_pool = _dedupe_choices(
            choice_pool + _fallback_distractors(correct_answer),
            exclude=set(),
        )
    choice_pool = choice_pool[:4]
    if correct_answer not in choice_pool:
        choice_pool = [correct_answer, *choice_pool[:3]]
    rnd = random.Random(f"{question}|{correct_answer}|{grade}|{topic}")
    rnd.shuffle(choice_pool)
    return choice_pool, choice_pool.index(correct_answer), used_fallback


def evaluate_question_quality(
    *,
    question_text: str,
    answer_text: str,
    question_type: str,
    topic: str,
    grade: int,
) -> dict:
    topic_label = TOPIC_LABELS.get(topic, topic)
    user_prompt = (
        f"초등학교 {grade}학년용 {topic_label} 문제를 평가하세요.\n"
        f"문제 형식: {question_type}\n"
        f"문제: {question_text}\n"
        f"정답: {answer_text}\n"
        "다음 JSON만 출력하세요:\n"
        '{"relevance":0,"clarity":0,"difficulty":0,"overall":0,"approved":true,"feedback":"짧은 한 줄"}\n'
        "규칙: 0~100 정수, approved는 overall이 40 이상이면 true."
    )
    payload = _call_ai_json(
        system_prompt=QUALITY_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    relevance = max(0, min(100, int(payload.get("relevance", 0) or 0)))
    clarity = max(0, min(100, int(payload.get("clarity", 0) or 0)))
    difficulty = max(0, min(100, int(payload.get("difficulty", 0) or 0)))
    overall = max(0, min(100, int(payload.get("overall", 0) or 0)))
    approved = bool(payload.get("approved", overall >= 40))
    feedback = str(payload.get("feedback") or "").strip()[:200]
    return {
        "relevance": relevance,
        "clarity": clarity,
        "difficulty": difficulty,
        "overall": overall,
        "approved": approved,
        "feedback": feedback or "평가가 완료됐습니다.",
        "fallback_used": False,
    }


def fallback_quality_result() -> dict:
    return {
        "relevance": 0,
        "clarity": 0,
        "difficulty": 0,
        "overall": 0,
        "approved": False,
        "feedback": "AI 확인이 늦어져서 선생님 확인으로 넘겼습니다.",
        "fallback_used": True,
    }


def calculate_base_points(quality_score: int) -> int:
    score = max(0, min(100, int(quality_score or 0)))
    if score < 40:
        return 0
    if score >= 80:
        return 40 + min(10, math.floor((score - 80) / 2))
    if score >= 60:
        return 25 + min(14, math.floor((score - 60) * 14 / 19))
    return 10 + min(14, math.floor((score - 40) * 14 / 19))
